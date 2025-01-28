import os
import re
from datetime import datetime, timedelta
import schedule
from selenium import webdriver
from selenium.common import NoSuchElementException
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
import time
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# 환경변수 설정 가져오기
load_dotenv()
options = Options()
options.add_argument("--headless")
g_reload_flag = False

class ReservationBot():
    def __init__(self):
        # selenium 설정
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 10)  # 최대 10초 동안 대기

        # slack bot
        self.slack_token = os.getenv("SLACK_BOT_TOKEN")
        self.slack_client = WebClient(token=self.slack_token)
        self.channel_id = os.getenv("SLACK_CHANNEL")
        self.user_id = os.getenv("KORAIL_USER_ID")
        self.user_password = os.getenv("KORAIL_USER_PASSWORD")

    def send_slack_message(self, message):
        try:
            self.slack_client.chat_postMessage(
                channel=self.channel_id,
                text=message
            )
        except SlackApiError as e:
            print(f"Error sending message: {e}")

    def login(self):
        # 페이지 이동
        self.driver.get("https://www.letskorail.com/korail/com/login.do")

        # 명시적 대기, ID 입력 필드 대기
        self.wait.until(EC.presence_of_element_located((By.ID, "txtMember")))

        # 아이디 입력
        self.driver.find_element(By.ID, "txtMember").send_keys(self.user_id)
        self.driver.find_element(By.ID, "txtPwd").send_keys(self.user_password)

        # 로그인 버튼 클릭
        self.driver.find_element(By.XPATH, '//*[@id="loginDisplay1"]/ul/li[3]/a/img').click()

        # 로드 완료 대기
        self.wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#header > div.lnb > div.lnb_m01 > h3 > a > img"))).click()
        print("로그인 성공")


    def search_start_city(self, city):
        start_city = self.driver.find_element(By.ID, "start")
        start_city.clear()
        start_city.send_keys(city)
        start_city.send_keys(Keys.RETURN)
        print(f"출발지 {city} 입력 완료")

    def korail_arrival_city(self, city):
        arrival_city = self.driver.find_element(By.ID, "get")
        arrival_city.clear()
        arrival_city.send_keys(city)
        arrival_city.send_keys(Keys.RETURN)
        print(f"도착지 {city} 입력 완료")

    # 년 선택
    def korail_year_select(self, year="2025"):
        year_select = Select(self.driver.find_element(By.ID, "s_year"))
        year_select.select_by_value(year)
        print(f"년도 {year} 선택 완료")

    # 월 선택
    def korail_month_select(self, month="01"):
        month_select = Select(self.driver.find_element(By.ID, "s_month"))
        month_select.select_by_value(month)
        print(f"월 {month} 선택 완료")

    # 일 선택
    def korail_day_select(self, day="30"):
        day_select = Select(self.driver.find_element(By.ID, "s_day"))
        day_select.select_by_value(day)
        print(f"일 {day} 선택 완료")

    # 시간 선택
    def korail_hour_select(self, hour="15"):
        hour_select = Select(self.driver.find_element(By.ID, "s_hour"))
        hour_select.select_by_value(hour)
        print(f"시간 {hour} 선택 완료")

    # 검색 버튼 클릭
    def korail_search_button(self):
        try:
            # XPath로 버튼 찾기
            inquiry_button = self.driver.find_element(By.XPATH, "//img[@alt='조회하기']")

            # 버튼 클릭
            inquiry_button.click()

        except Exception as e:
            print(f"조회하기 버튼 클릭 에러: {e}")

    # 계속 검색
    def check_is_reserve(self, index_seq, reload_cnt):
        # 테이블의 모든 행 가져오기
        rows = self.driver.find_elements(By.XPATH, "//tbody/tr")
        total_rows = len(rows)  # 총 행 개수
        print(f"테이블에 있는 총 행 개수: {total_rows}")

        # 예약 시간 정보 딕셔너리
        reserve_dict = {
            1: "15:00",
            2: "20:00"
        }

        # while문 flag
        found_reservation = False
        while not found_reservation:
            # 현재 시간 가져오기
            now_time = datetime.now()
            now_time_str = now_time.strftime("%Y년 %m월 %d일 %H시 %M분 %S초")
            now_time_min = now_time.strftime("%M")

            # 15시, 20시 2개 검색
            for i in index_seq:
                reserve_button = None

                # reserve_button 찾기 시도 (못 찾는 경우도 간혹 있음)
                while reserve_button is None:
                    try:
                        reserve_button = self.driver.find_element(
                            By.XPATH,
                            f"//*[@id='tableResult']/tbody/tr[{i}]/td[6]/img"
                        )
                    except NoSuchElementException:
                        print(f"{reserve_dict.get(i)} 예약 시도 시, element를 찾지 못했습니다.")
                        self.korail_search_button()
                        time.sleep(5)
                        reload_cnt += 1

                        # 안되면, 로그인부터 다시 시도
                        if reload_cnt > 7:
                            self.reload_login()
                            # 5초 검색 대기
                            time.sleep(5)

                print(f"{now_time_str}| {reserve_dict.get(i)}시 예약 상태: {reserve_button.get_attribute('alt')}")

                # 좌석인 지
                if reserve_button.get_attribute("alt") == "예약하기":
                    self.driver.find_element(By.XPATH,
                                             "/html/body/div[1]/div[3]/div/div[1]/form[1]/div/div[4]/table[1]/tbody/tr[%s]/td[6]/a[1]/img" % i).click()

                    reserve_button.click()
                    self.send_slack_message("🚨 앉아서 가기 예약 가능! 페이지로 이동합니다.")
                    found_reservation = True
                    break

                # 입석 포함인 지
                elif reserve_button.get_attribute("alt") == "입좌석묶음예약":
                    self.driver.find_element(By.XPATH,
                                             "/html/body/div[1]/div[3]/div/div[1]/form[1]/div/div[4]/table[1]/tbody/tr[%s]/td[6]/a[1]/img" % i).click()

                    reserve_button.click()
                    self.send_slack_message("🚨 입+좌석 예약 가능! 페이지로 이동합니다.")
                    found_reservation = True
                    break

            if not found_reservation:
                # 매시간 정각마다 slack 전송
                if now_time_min == "00" or now_time_min == "30":
                    self.send_slack_message(f"❌ {now_time_str} 현재, 아직 모두 매진입니다")

                # 반복은 계속 적용
                self.korail_search_button()
                time.sleep(4)

            else:
                self.send_slack_message(f"✅ {now_time_str} 현재, 10분 내로 예약해야합니다")

    def reload_login(self):
        self.login()
        self.search_start_city("충주")
        self.korail_arrival_city("판교(경기)")
        self.korail_year_select("2025")
        self.korail_month_select("01")
        self.korail_day_select("30")
        self.korail_hour_select("15")
        self.korail_search_button()

if __name__ == '__main__':
    reservation_bot = ReservationBot()
    reload_cnt = 0

    reservation_bot.login()
    reservation_bot.search_start_city("충주")
    reservation_bot.korail_arrival_city("판교(경기)")
    reservation_bot.korail_year_select("2025")
    reservation_bot.korail_month_select("01")
    reservation_bot.korail_day_select("30")
    reservation_bot.korail_hour_select("15")
    reservation_bot.korail_search_button()

    # 5초 대기 후 검색 시작
    time.sleep(5)
    reservation_bot.check_is_reserve([1, 2], reload_cnt)

