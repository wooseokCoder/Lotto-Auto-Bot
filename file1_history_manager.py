import requests
import csv
import os
import re
import concurrent.futures
import time
from bs4 import BeautifulSoup

# --- 경로 설정 ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(SCRIPT_DIR, 'lotto_history.csv')
BASE_URL = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def get_last_drw_no():
    if not os.path.exists(CSV_FILE):
        return 0

    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = [r for r in reader if r]
        if not rows or len(rows) <= 1:
            return 0
        try:
            return int(rows[-1][0])
        except:
            return 0

def fetch_one_round(drw_no):
    """한 회차의 정보를 가져오는 함수 (동행복권 API 우선, 실패시 네이버 검색 폴백)"""
    # 1. 동행복권 API 시도
    try:
        resp = requests.get(f"{BASE_URL}&drwNo={drw_no}", headers=HEADERS, timeout=3)
        data = resp.json()
        if data.get("returnValue") == "success":
            return [
                data["drwNo"],
                data["drwtNo1"], data["drwtNo2"], data["drwtNo3"],
                data["drwtNo4"], data["drwtNo5"], data["drwtNo6"],
                data["bnusNo"]
            ]
    except Exception:
        pass

    # 2. 네이버 검색 폴백
    try:
        url = f"https://search.naver.com/search.naver?query={drw_no}회로또당첨번호"
        resp = requests.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        spans = soup.find_all('span', class_=re.compile(r'ball|num'))
        nums = [int(s.text.strip()) for s in spans if s.text.strip().isdigit() and 1 <= int(s.text.strip()) <= 45]
        if len(nums) >= 7 and len(set(nums[:6])) == 6:
            return [drw_no] + nums[:7]
    except Exception as e:
        print(f"[{drw_no}회] 통신 실패: {e}")
    return None

def get_latest_official_round():
    """현재 기준 가장 최신 회차 번호를 추정"""
    try:
        url = "https://search.naver.com/search.naver?query=로또당첨번호"
        resp = requests.get(url, headers=HEADERS, timeout=5)
        matches = [int(m) for m in re.findall(r'(\d+)회', resp.text) if 1000 <= int(m) <= 2500]
        if matches:
            candidate = max(matches)
            for drw in range(candidate, candidate - 5, -1):
                data = fetch_one_round(drw)
                if data:
                    prev_data = fetch_one_round(drw - 1)
                    if prev_data and data[1:] == prev_data[1:]:
                        continue
                    return drw
    except Exception as e:
        print(f"최신 회차 조회 실패: {e}")

    last = get_last_drw_no()
    return last if last > 0 else 1246

def update_history():
    print(f"### 로또 데이터 고속 업데이트 (Multi-threading) ###")
    last_drw = get_last_drw_no()

    print("최신 회차 정보를 확인 중입니다...")
    latest_drw = get_latest_official_round()

    if last_drw >= latest_drw:
        print(f"이미 최신 데이터입니다 ({last_drw}회). 업데이트할 내용이 없습니다.")
        return

    start_drw = last_drw + 1
    end_drw = latest_drw
    total_to_fetch = end_drw - start_drw + 1

    print(f"업데이트 구간: {start_drw}회 ~ {end_drw}회 (총 {total_to_fetch}건)")
    print("고속 다운로드를 시작합니다... (잠시만 기다려주세요)")

    new_data = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_drw = {executor.submit(fetch_one_round, i): i for i in range(start_drw, end_drw + 1)}

        completed = 0
        for future in concurrent.futures.as_completed(future_to_drw):
            result = future.result()
            if result:
                new_data.append(result)

            completed += 1
            if completed % 10 == 0 or completed == total_to_fetch:
                print(f"-> 진행률: {completed}/{total_to_fetch} ({(completed/total_to_fetch)*100:.1f}%)", end='\r')

    print("\n데이터 정렬 및 저장 중...")

    new_data.sort(key=lambda x: x[0])

    if new_data:
        mode = 'a' if os.path.exists(CSV_FILE) else 'w'
        with open(CSV_FILE, mode, newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if mode == 'w':
                writer.writerow(["DrwNo", "N1", "N2", "N3", "N4", "N5", "N6", "Bonus"])
            writer.writerows(new_data)
        print(f"✅ 업데이트 완료! 총 {len(new_data)}건이 추가되었습니다. (마지막 회차: {new_data[-1][0]}회)")
    else:
        print("추가할 데이터가 없습니다.")

if __name__ == "__main__":
    start_time = time.time()
    update_history()
    print(f"소요 시간: {time.time() - start_time:.2f}초")
