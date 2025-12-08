import requests
import csv
import os
import concurrent.futures
import time

# --- 경로 설정 ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(SCRIPT_DIR, 'lotto_history.csv')
BASE_URL = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber"

def get_last_drw_no():
    if not os.path.exists(CSV_FILE):
        return 0
    
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
        if not rows or len(rows) <= 1: 
            return 0
        try:
            return int(rows[-1][0])
        except:
            return 0

def fetch_one_round(drw_no):
    """한 회차의 정보를 가져오는 함수 (병렬 처리를 위해 분리)"""
    try:
        resp = requests.get(f"{BASE_URL}&drwNo={drw_no}", timeout=5)
        data = resp.json()
        
        if data["returnValue"] == "fail":
            return None
        
        return [
            data["drwNo"],
            data["drwtNo1"], data["drwtNo2"], data["drwtNo3"],
            data["drwtNo4"], data["drwtNo5"], data["drwtNo6"],
            data["bnusNo"]
        ]
    except Exception as e:
        print(f"[{drw_no}회] 통신 실패: {e}")
        return None

def get_latest_official_round():
    """현재 기준 가장 최신 회차 번호를 추정"""
    # 1100회부터 시작해서 미래의 회차를 찔러보며 최신 회차 찾기
    # 너무 오래 걸리지 않게 대략적인 최근 회차(예: 1150) 근처에서 탐색
    start_guess = 1150
    while True:
        resp = requests.get(f"{BASE_URL}&drwNo={start_guess}")
        if resp.json()["returnValue"] == "fail":
            return start_guess - 1
        start_guess += 1

def update_history():
    print(f"### 로또 데이터 고속 업데이트 (Multi-threading) ###")
    last_drw = get_last_drw_no()
    
    # 최신 회차 확인 (API로 마지막 번호 확인)
    print("최신 회차 정보를 확인 중입니다...")
    latest_drw = get_latest_official_round()
    
    if last_drw >= latest_drw:
        print("이미 최신 데이터입니다. 업데이트할 내용이 없습니다.")
        return

    start_drw = last_drw + 1
    end_drw = latest_drw
    total_to_fetch = end_drw - start_drw + 1
    
    print(f"업데이트 구간: {start_drw}회 ~ {end_drw}회 (총 {total_to_fetch}건)")
    print("고속 다운로드를 시작합니다... (잠시만 기다려주세요)")

    new_data = []
    
    # 병렬 처리 시작 (동시에 20개씩 요청)
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        # 작업 예약
        future_to_drw = {executor.submit(fetch_one_round, i): i for i in range(start_drw, end_drw + 1)}
        
        completed = 0
        for future in concurrent.futures.as_completed(future_to_drw):
            result = future.result()
            if result:
                new_data.append(result)
            
            # 진행률 표시
            completed += 1
            if completed % 10 == 0 or completed == total_to_fetch:
                print(f"-> 진행률: {completed}/{total_to_fetch} ({(completed/total_to_fetch)*100:.1f}%)", end='\r')

    print("\n데이터 정렬 및 저장 중...")
    
    # 병렬 처리는 순서가 뒤죽박죽이므로 회차순 정렬 필수
    new_data.sort(key=lambda x: x[0])

    if new_data:
        mode = 'a' if os.path.exists(CSV_FILE) else 'w'
        with open(CSV_FILE, mode, newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if mode == 'w':
                writer.writerow(["DrwNo", "N1", "N2", "N3", "N4", "N5", "N6", "Bonus"])
            writer.writerows(new_data)
        print(f"✅ 업데이트 완료! 총 {len(new_data)}건이 추가되었습니다.")
    else:
        print("추가할 데이터가 없습니다.")

if __name__ == "__main__":
    start_time = time.time()
    update_history()
    print(f"소요 시간: {time.time() - start_time:.2f}초")