import csv
import json
import random
import os
import argparse
import sys
from datetime import datetime

# 구글 시트 라이브러리
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 경로 설정 ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(SCRIPT_DIR, 'lotto_history.csv')
MY_PICKS_FILE = os.path.join(SCRIPT_DIR, 'my_picks.json')
JSON_KEY_FILE = os.path.join(SCRIPT_DIR, 'lotto_key.json')

# 구글 시트 설정
GOOGLE_SHEET_NAME = '로또기록표'
SHEET1_NAME = '결과기록'   # 결과 누적용
SHEET2_NAME = '이번주번호' # 이번주 번호 10개용

class LottoEngine:
    def __init__(self):
        self.history_set = set()
        self.latest_draw = None
        self.load_history()

    def load_history(self):
        if not os.path.exists(HISTORY_FILE):
            return
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if not row: continue
                    nums = tuple(sorted([int(x) for x in row[1:7]]))
                    self.history_set.add(nums)
                    self.latest_draw = {
                        "drwNo": int(row[0]),
                        "winning_nums": set([int(x) for x in row[1:7]]),
                        "bonus": int(row[7])
                    }
        except: pass

    # --- 필터링 로직 ---
    def check_filters(self, numbers):
        consecutive_cnt = 0
        for i in range(len(numbers) - 1):
            if numbers[i+1] - numbers[i] == 1:
                consecutive_cnt += 1
                if consecutive_cnt >= 3: return False
            else: consecutive_cnt = 0

        if not (100 <= sum(numbers) <= 180): return False

        diffs = set()
        for i in range(6):
            for j in range(i + 1, 6):
                diffs.add(numbers[j] - numbers[i])
        if (len(diffs) - 5) < 7: return False

        return True

    def generate_numbers(self, count=15):
        results = []
        target_drw_no = (self.latest_draw['drwNo'] + 1) if self.latest_draw else 1

        print(f"[{target_drw_no}회차] 번호 생성 중...")
        attempts = 0
        while len(results) < count:
            attempts += 1
            candidate = sorted(random.sample(range(1, 46), 6))
            if tuple(candidate) in self.history_set: continue
            if not self.check_filters(candidate): continue
            results.append(candidate)
            if attempts % 10000 == 0: print(f"{attempts}...", end='\r')

        save_data = { "target_drw_no": target_drw_no, "picks": results }
        with open(MY_PICKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=4)

        print(f"\n-> {count}게임 생성 완료.")

        # 시트2에 이번주 번호 업로드
        self.upload_picks_to_sheet(target_drw_no, results)

    def check_my_rank(self):
        if not os.path.exists(MY_PICKS_FILE):
            print("파일 없음.")
            return

        with open(MY_PICKS_FILE, 'r', encoding='utf-8') as f:
            my_data = json.load(f)

        target_round = my_data['target_drw_no']
        my_numbers = my_data['picks']

        winning_info = None
        if os.path.exists(HISTORY_FILE):
             with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = [r for r in reader if r]
                for row in rows[1:]: # 헤더 제외
                    if row[0] == str(target_round):
                        winning_info = {"nums": set([int(x) for x in row[1:7]]), "bonus": int(row[7])}
                        break

                # 지정 회차 결과가 없으면 가장 최근 추첨 회차 결과로 대체
                if not winning_info and len(rows) > 1:
                    last_row = rows[-1]
                    target_round = int(last_row[0])
                    winning_info = {"nums": set([int(x) for x in last_row[1:7]]), "bonus": int(last_row[7])}
                    print(f"[안내] 지정된 회차 데이터가 없어 가장 최근 회차({target_round}회차) 결과로 진행합니다.")

        if not winning_info:
            print("당첨 번호 이력 데이터(lotto_history.csv)가 존재하지 않습니다.")
            return

        print(f"### {target_round}회차 당첨 확인 ###")

        best_result = {"rank_val": 7, "rank_str": "낙첨", "matched": 0, "nums": []}

        for nums in my_numbers:
            matched = len(winning_info['nums'].intersection(set(nums)))
            is_bonus = winning_info['bonus'] in nums

            rank_val, rank_str = 7, "낙첨"
            if matched == 6: rank_val, rank_str = 1, "1등"
            elif matched == 5 and is_bonus: rank_val, rank_str = 2, "2등"
            elif matched == 5: rank_val, rank_str = 3, "3등"
            elif matched == 4: rank_val, rank_str = 4, "4등"
            elif matched == 3: rank_val, rank_str = 5, "5등"

            if rank_val < best_result["rank_val"]:
                best_result = {"rank_val": rank_val, "rank_str": rank_str, "matched": matched, "nums": nums}
            elif rank_val == best_result["rank_val"] and matched > best_result["matched"]:
                 best_result = {"rank_val": rank_val, "rank_str": rank_str, "matched": matched, "nums": nums}

        print(f"결과: {best_result['rank_str']} (일치: {best_result['matched']}개)")

        # 시트1에 결과 기록 업로드
        self.upload_result_to_sheet(target_round, best_result)

    # --- 구글 시트 연동 함수들 ---
    def get_gspread_client(self):
        if not os.path.exists(JSON_KEY_FILE):
            print("[패스] lotto_key.json 인증 키 파일이 없습니다.")
            return None
        try:
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_KEY_FILE, scope)
            return gspread.authorize(creds)
        except Exception as e:
            print(f"[에러] 구글 시트 API 인증 실패: {e}")
            return None

    def upload_picks_to_sheet(self, round_no, picks):
        """[시트2] 이번주 번호 업데이트 (기존 내용 지움)"""
        client = self.get_gspread_client()
        if not client: return

        try:
            try:
                sheet = client.open(GOOGLE_SHEET_NAME).worksheet(SHEET2_NAME)
            except Exception:
                print(f"[경고] 구글 시트 문서('{GOOGLE_SHEET_NAME}') 또는 탭('{SHEET2_NAME}')을 찾을 수 없습니다.")
                return

            print("구글 시트(이번주번호) 업데이트 중...", end='')
            sheet.clear()
            header = ["생성일시", "회차", "번호1", "번호2", "번호3", "번호4", "번호5", "번호6"]
            sheet.append_row(header)

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            rows = []
            for nums in picks:
                row = [now_str, f"{round_no}회"] + nums
                rows.append(row)

            sheet.append_rows(rows)
            print(" -> 성공!")

        except Exception as e:
            print(f"\n[업로드 실패] {e}")

    def upload_result_to_sheet(self, round_no, result):
        """[시트1] 결과 누적 기록 (행 추가)"""
        client = self.get_gspread_client()
        if not client: return

        try:
            try:
                sheet = client.open(GOOGLE_SHEET_NAME).worksheet(SHEET1_NAME)
            except Exception:
                print(f"[경고] 구글 시트 문서('{GOOGLE_SHEET_NAME}') 또는 탭('{SHEET1_NAME}')을 찾을 수 없습니다.")
                return

            print("구글 시트(결과기록) 저장 중...", end='')

            if not sheet.row_values(1):
                sheet.append_row(["날짜", "회차", "결과", "일치수", "내번호"])

            row_data = [
                datetime.now().strftime("%Y-%m-%d"),
                f"{round_no}회",
                result['rank_str'],
                f"{result['matched']}개",
                str(result['nums'])
            ]
            sheet.append_row(row_data)
            print(" -> 성공!")

        except Exception as e:
            print(f"\n[업로드 실패] {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['gen', 'check'], required=False)
    args = parser.parse_args()

    engine = LottoEngine()

    mode = args.mode
    if not mode:
        print("1. 번호 생성 (gen)\n2. 결과 확인 (check)")
        sel = input("선택: ").strip()
        mode = 'gen' if sel in ['1', 'gen'] else 'check'

    if mode == 'gen':
        engine.generate_numbers(15)
    elif mode == 'check':
        engine.check_my_rank()
