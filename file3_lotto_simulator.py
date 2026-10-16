import csv
import os
import random
import argparse
import time
import threading
from typing import Dict, List, Set, Tuple, Any, Optional

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(SCRIPT_DIR, 'lotto_history.csv')

# Fixed prize money assumptions (KRW)
DEFAULT_PRIZES = {
    1: 2_000_000_000,  # 1등: 약 20억원
    2: 50_000_000,     # 2등: 약 5,000만원
    3: 1_500_000,      # 3등: 약 150만원
    4: 50_000,         # 4등: 5만원
    5: 5_000,          # 5등: 5천원
    7: 0               # 낙첨: 0원
}

PRICE_PER_GAME = 1_000  # 게임당 1,000원


def check_filters_with_reason(numbers: List[int]) -> Tuple[bool, List[str]]:
    """번호 조합 필터링 검증 및 실패 사유 반환"""
    reasons = []

    # 1. 3연속 이상 번호 제외
    consecutive_cnt = 0
    for i in range(len(numbers) - 1):
        if numbers[i + 1] - numbers[i] == 1:
            consecutive_cnt += 1
            if consecutive_cnt >= 2:  # 연속 인접 차이 1이 2번 발생하면 3연속 수
                reasons.append(f"3연속 이상 번호 포함 (예: {numbers[i-1]}, {numbers[i]}, {numbers[i+1]})")
                break
        else:
            consecutive_cnt = 0

    # 2. 총합 범위 (100 ~ 180)
    total_sum = sum(numbers)
    if not (100 <= total_sum <= 180):
        reasons.append(f"총합 범위 벗어남 (현재: {total_sum}, 조건: 100~180)")

    # 3. 고유 차이값 개수 조건
    diffs = set()
    for i in range(6):
        for j in range(i + 1, 6):
            diffs.add(numbers[j] - numbers[i])
    unique_diff_metric = len(diffs) - 5
    if unique_diff_metric < 7:
        reasons.append(f"고유 차이값 패턴 조건 미달 (현재 지표: {unique_diff_metric}, 최소 기준: 7)")

    is_valid = (len(reasons) == 0)
    return is_valid, reasons


def check_filters(numbers: List[int]) -> bool:
    """번호 조합 필터링 검증"""
    valid, _ = check_filters_with_reason(numbers)
    return valid


def evaluate_ticket(picked: List[int], winning_nums: Set[int], bonus: int) -> Tuple[int, str, int, bool]:
    """선택한 번호 1줄과 당첨 번호를 비교하여 등수 판정"""
    matched = len(winning_nums.intersection(set(picked)))
    is_bonus = bonus in picked

    if matched == 6:
        return 1, "1등", matched, is_bonus
    elif matched == 5 and is_bonus:
        return 2, "2등", matched, is_bonus
    elif matched == 5:
        return 3, "3등", matched, is_bonus
    elif matched == 4:
        return 4, "4등", matched, is_bonus
    elif matched == 3:
        return 5, "5등", matched, is_bonus
    else:
        return 7, "낙첨", matched, is_bonus


def load_history(filepath: str = HISTORY_FILE) -> Dict[int, Dict[str, Any]]:
    """lotto_history.csv 파일을 읽어 회차별 당첨 정보를 반환"""
    history = {}
    if not os.path.exists(filepath):
        return history

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if not row or len(row) < 8:
                continue
            drw_no = int(row[0])
            nums = sorted([int(x) for x in row[1:7]])
            bonus = int(row[7])
            history[drw_no] = {
                "drwNo": drw_no,
                "nums_list": nums,
                "winning_nums": set(nums),
                "nums_tuple": tuple(nums),
                "bonus": bonus
            }
    return history


class LottoSimulator:
    def __init__(self, history_filepath: str = HISTORY_FILE):
        self.history = load_history(history_filepath)

    def is_target_generatable(self, target_drw_no: int) -> Tuple[bool, Dict[str, Any]]:
        if target_drw_no not in self.history:
            return False, {"error": f"{target_drw_no}회차 데이터가 존재하지 않습니다."}

        target_info = self.history[target_drw_no]
        winning_nums = target_info["nums_list"]
        winning_tuple = target_info["nums_tuple"]

        past_history_set = {
            info["nums_tuple"]
            for d, info in self.history.items()
            if d < target_drw_no
        }

        reasons = []
        if winning_tuple in past_history_set:
            reasons.append("역대 과거 회차에서 이미 출현했던 당첨 번호 조합입니다 (과거 재출현 필터 적용).")

        valid_filter, filter_reasons = check_filters_with_reason(winning_nums)
        reasons.extend(filter_reasons)

        can_generate = (len(reasons) == 0)

        return can_generate, {
            "target_drw_no": target_drw_no,
            "winning_nums": winning_nums,
            "bonus": target_info["bonus"],
            "can_generate": can_generate,
            "reasons": reasons
        }

    def simulate_attempts_for_target(self, target_drw_no: int, max_attempts: int = 50_000_000,
                                     callback=None) -> Dict[str, Any]:
        can_generate, eval_info = self.is_target_generatable(target_drw_no)
        if not can_generate:
            return {
                "error": "해당 회차 당첨 번호는 로또봇 필터 조건에 의해 생성 불가능한 조합입니다.",
                "eval_info": eval_info
            }

        target_tuple = tuple(eval_info["winning_nums"])
        past_history_set = {
            info["nums_tuple"]
            for d, info in self.history.items()
            if d < target_drw_no
        }

        attempts = 0
        start_time = time.time()
        batch_size = 100_000

        while attempts < max_attempts:
            attempts += 1
            candidate = sorted(random.sample(range(1, 46), 6))

            if tuple(candidate) in past_history_set:
                continue

            if not check_filters(candidate):
                continue

            if tuple(candidate) == target_tuple:
                elapsed = time.time() - start_time
                cost = attempts * PRICE_PER_GAME
                res = {
                    "target_drw_no": target_drw_no,
                    "winning_nums": eval_info["winning_nums"],
                    "attempts": attempts,
                    "elapsed_sec": round(elapsed, 2),
                    "virtual_cost_krw": cost,
                    "found": True
                }
                if callback:
                    callback(res, False)
                return res

            if callback and attempts % batch_size == 0:
                elapsed = time.time() - start_time
                callback({
                    "attempts": attempts,
                    "elapsed_sec": round(elapsed, 1)
                }, True)

        res = {
            "target_drw_no": target_drw_no,
            "winning_nums": eval_info["winning_nums"],
            "attempts": attempts,
            "elapsed_sec": round(time.time() - start_time, 2),
            "virtual_cost_krw": attempts * PRICE_PER_GAME,
            "found": False,
            "message": f"최대 제한 시도 횟수({max_attempts:,}회) 내에 출현하지 않았습니다."
        }
        if callback:
            callback(res, False)
        return res

    def generate_numbers_for_round(self, target_drw_no: int, history_set_before_target: Set[Tuple[int, ...]],
                                   count: int = 15, use_filter: bool = True) -> List[List[int]]:
        results = []
        attempts = 0
        max_attempts = 100_000

        while len(results) < count and attempts < max_attempts:
            attempts += 1
            candidate = sorted(random.sample(range(1, 46), 6))

            if tuple(candidate) in history_set_before_target:
                continue

            if use_filter and not check_filters(candidate):
                continue

            results.append(candidate)

        return results

    def run_simulation(self, start_drw: int, end_drw: int, games_per_round: int = 15,
                       use_filter: bool = True, trials: int = 1) -> Dict[str, Any]:
        available_drws = [d for d in range(start_drw, end_drw + 1) if d in self.history]
        if not available_drws:
            return {"error": "지정한 회차 구간의 당첨 데이터가 존재하지 않습니다."}

        total_games = 0
        total_prize = 0
        rank_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 7: 0}

        for trial in range(trials):
            for drw_no in available_drws:
                past_history_set = {
                    info["nums_tuple"]
                    for d, info in self.history.items()
                    if d < drw_no
                }

                winning_info = self.history[drw_no]
                winning_nums = winning_info["winning_nums"]
                bonus = winning_info["bonus"]

                picks = self.generate_numbers_for_round(
                    target_drw_no=drw_no,
                    history_set_before_target=past_history_set,
                    count=games_per_round,
                    use_filter=use_filter
                )

                for ticket in picks:
                    total_games += 1
                    rank, rank_str, matched, is_bonus = evaluate_ticket(ticket, winning_nums, bonus)
                    rank_counts[rank] += 1
                    total_prize += DEFAULT_PRIZES[rank]

        total_cost = total_games * PRICE_PER_GAME
        profit = total_prize - total_cost
        roi = (total_prize / total_cost * 100) if total_cost > 0 else 0.0

        return {
            "start_drw": start_drw,
            "end_drw": end_drw,
            "simulated_rounds": len(available_drws),
            "trials": trials,
            "games_per_round": games_per_round,
            "total_games": total_games,
            "total_cost": total_cost,
            "total_prize": total_prize,
            "profit": profit,
            "roi": roi,
            "rank_counts": rank_counts,
            "use_filter": use_filter
        }


if HAS_TKINTER:
    class LottoSimulatorGUI:
        def __init__(self, root: tk.Tk):
            self.root = root
            self.root.title("🎰 로또봇 백테스팅 & 시뮬레이터")
            self.root.geometry("780x680")

            self.simulator = LottoSimulator()
            if not self.simulator.history:
                messagebox.showerror("오류", "lotto_history.csv 파일을 찾을 수 없거나 비어 있습니다.")
                return

            self.all_drws = sorted(list(self.simulator.history.keys()), reverse=True)
            self.create_widgets()

        def create_widgets(self):
            # Top Frame: 회차 선택 콤보박스
            top_frame = ttk.LabelFrame(self.root, text=" 🎯 특정 회차 타겟 시뮬레이션 ", padding=10)
            top_frame.pack(fill="x", padx=15, pady=10)

            ttk.Label(top_frame, text="회차 선택:").grid(row=0, column=0, padx=5, pady=5)

            self.combo_drw = ttk.Combobox(top_frame, values=[f"{d}회" for d in self.all_drws], width=15, state="readonly")
            if self.all_drws:
                self.combo_drw.current(0)
            self.combo_drw.grid(row=0, column=1, padx=5, pady=5)

            btn_check = ttk.Button(top_frame, text="1등 생성 가능 여부 분석", command=self.on_check_generatable)
            btn_check.grid(row=0, column=2, padx=5, pady=5)

            btn_run = ttk.Button(top_frame, text="1등 포착 시도 횟수 측정 🚀", command=self.on_run_attempts)
            btn_run.grid(row=0, column=3, padx=5, pady=5)

            # Middle Frame: 구간 백테스팅
            mid_frame = ttk.LabelFrame(self.root, text=" 📊 구간 백테스팅 & 전략 비교 ", padding=10)
            mid_frame.pack(fill="x", padx=15, pady=5)

            ttk.Label(mid_frame, text="시작 회차:").grid(row=0, column=0, padx=5, pady=5)
            self.combo_start = ttk.Combobox(mid_frame, values=[f"{d}회" for d in sorted(self.all_drws)], width=10, state="readonly")
            self.combo_start.set(f"{min(self.all_drws)}회")
            self.combo_start.grid(row=0, column=1, padx=5, pady=5)

            ttk.Label(mid_frame, text="종료 회차:").grid(row=0, column=2, padx=5, pady=5)
            self.combo_end = ttk.Combobox(mid_frame, values=[f"{d}회" for d in sorted(self.all_drws)], width=10, state="readonly")
            self.combo_end.set(f"{max(self.all_drws)}회")
            self.combo_end.grid(row=0, column=3, padx=5, pady=5)

            btn_backtest = ttk.Button(mid_frame, text="전략 비교 백테스팅 (필터 ON vs OFF)", command=self.on_run_backtest)
            btn_backtest.grid(row=0, column=4, padx=10, pady=5)

            # Log Frame: ScrolledText
            log_frame = ttk.LabelFrame(self.root, text=" 📜 시뮬레이션 결과 및 로그 ", padding=10)
            log_frame.pack(fill="both", expand=True, padx=15, pady=10)

            self.txt_log = scrolledtext.ScrolledText(log_frame, wrap="word", font=("Courier", 10))
            self.txt_log.pack(fill="both", expand=True)

            self.log("✨ 로또봇 시뮬레이터 프로그램에 오신 것을 환영합니다!")
            self.log(f"• 현재 탑재된 역대 당첨 데이터: 1회 ~ {max(self.all_drws)}회")
            self.log("• 상단 콤보박스에서 회차를 선택하여 1등 번호 생성 테스트를 진행하세요.\n" + "="*65)

        def log(self, msg: str):
            self.txt_log.insert(tk.END, msg + "\n")
            self.txt_log.see(tk.END)

        def clear_log(self):
            self.txt_log.delete("1.0", tk.END)

        def get_selected_drw(self, combo: ttk.Combobox) -> int:
            val = combo.get().replace("회", "").strip()
            return int(val) if val.isdigit() else 0

        def on_check_generatable(self):
            drw = self.get_selected_drw(self.combo_drw)
            if not drw:
                messagebox.showwarning("경고", "회차를 선택해주세요.")
                return

            can_gen, info = self.simulator.is_target_generatable(drw)
            self.clear_log()
            self.log("=" * 65)
            self.log(f" 🎯 [{drw}회차] 로또봇 1등 번호 생성 가능 여부 분석")
            self.log("=" * 65)
            self.log(f"• 1등 당첨 번호: {info['winning_nums']} (보너스: {info['bonus']})")
            self.log(f"• 생성 가능 여부: {'✅ 생성 가능 (필터 조건 통과)' if can_gen else '❌ 생성 불가능 (필터 조건 위반)'}")

            if not can_gen:
                self.log("-" * 65)
                self.log(" ⚠️ 로또봇 추출 대상 제외 사유:")
                for idx, r in enumerate(info['reasons'], 1):
                    self.log(f"   {idx}. {r}")
                self.log("-" * 65)
                self.log("💡 이 회차의 1등 번호는 안전 필터 규칙에 의해 사전 차단되는 조합입니다.")

        def on_run_attempts(self):
            drw = self.get_selected_drw(self.combo_drw)
            if not drw:
                messagebox.showwarning("경고", "회차를 선택해주세요.")
                return

            can_gen, info = self.simulator.is_target_generatable(drw)
            if not can_gen:
                self.on_check_generatable()
                return

            self.clear_log()
            self.log(f"🚀 [{drw}회차] 1등 조합 {info['winning_nums']} 시뮬레이션 구동 시작...")
            self.log("로또봇 알고리즘으로 번호를 계속 추출 중입니다... 잠시만 기다려주세요.")

            def worker():
                def cb(data, is_intermediate):
                    if is_intermediate:
                        self.root.after(0, lambda: self.log(f" -> {data['attempts']:,}회 시도 중... (소요시간: {data['elapsed_sec']}초)"))
                    else:
                        self.root.after(0, lambda: self.display_attempts_result(data))

                self.simulator.simulate_attempts_for_target(drw, callback=cb)

            threading.Thread(target=worker, daemon=True).start()

        def display_attempts_result(self, res: dict):
            if res.get("found"):
                self.log("\n" + "=" * 65)
                self.log(f" 🎉 [{res['target_drw_no']}회차] 1등 조합 포착 성공!")
                self.log("=" * 65)
                self.log(f"• 목표 1등 번호 : {res['winning_nums']}")
                self.log(f"• 도달 시도 횟수 : {res['attempts']:,} 회")
                self.log(f"• 가상 구매 비용 : {res['virtual_cost_krw']:,} 원")
                self.log(f"• 시뮬레이션 소요시간 : {res['elapsed_sec']} 초")
                self.log("=" * 65)
            else:
                self.log(f"\n❌ {res.get('message')}")

        def on_run_backtest(self):
            start_drw = self.get_selected_drw(self.combo_start)
            end_drw = self.get_selected_drw(self.combo_end)

            if start_drw > end_drw:
                messagebox.showwarning("경고", "시작 회차는 종료 회차보다 작거나 같아야 합니다.")
                return

            self.clear_log()
            self.log(f"🚀 구간 백테스팅 구동 중 ({start_drw}회 ~ {end_drw}회)...")

            def worker():
                res_filtered = self.simulator.run_simulation(start_drw, end_drw, use_filter=True)
                res_unfiltered = self.simulator.run_simulation(start_drw, end_drw, use_filter=False)
                self.root.after(0, lambda: self.display_backtest_result(res_filtered, res_unfiltered))

            threading.Thread(target=worker, daemon=True).start()

        def display_backtest_result(self, res_f: dict, res_u: dict):
            self.log("=" * 65)
            self.log(f" 📊 필터 적용 (전략 ON) 백테스팅 결과")
            self.log("=" * 65)
            self.log(f"• 구매 게임 수 : {res_f['total_games']:,} 게임 | 총 투자금 : {res_f['total_cost']:,} 원")
            self.log(f"• 총 당첨 금액 : {res_f['total_prize']:,} 원 | 수익률 (ROI) : {res_f['roi']:.2f}%")
            self.log(f"• 등수 집계     : 1등:{res_f['rank_counts'][1]} / 2등:{res_f['rank_counts'][2]} / 3등:{res_f['rank_counts'][3]} / 4등:{res_f['rank_counts'][4]} / 5등:{res_f['rank_counts'][5]}")

            self.log("\n" + "=" * 65)
            self.log(f" 📊 필터 미적용 (전략 OFF / 순수 랜덤) 백테스팅 결과")
            self.log("=" * 65)
            self.log(f"• 구매 게임 수 : {res_u['total_games']:,} 게임 | 총 투자금 : {res_u['total_cost']:,} 원")
            self.log(f"• 총 당첨 금액 : {res_u['total_prize']:,} 원 | 수익률 (ROI) : {res_u['roi']:.2f}%")
            self.log(f"• 등수 집계     : 1등:{res_u['rank_counts'][1]} / 2등:{res_u['rank_counts'][2]} / 3등:{res_u['rank_counts'][3]} / 4등:{res_u['rank_counts'][4]} / 5등:{res_u['rank_counts'][5]}")
            self.log("=" * 65)


def print_target_analysis_report(simulator: LottoSimulator, target_drw_no: int):
    can_generate, eval_info = simulator.is_target_generatable(target_drw_no)

    print("\n" + "=" * 65)
    print(f" 🎯 [{target_drw_no}회차] 로또봇 1등 번호 생성 가능 여부 분석")
    print("=" * 65)
    if "error" in eval_info:
        print(f"❌ 오류: {eval_info['error']}")
        return

    print(f"• 해당 회차 1등 당첨 번호 : {eval_info['winning_nums']} (보너스: {eval_info['bonus']})")
    print(f"• 로또봇 생성 가능 여부  : {'✅ 생성 가능 (필터 조건 통과)' if can_generate else '❌ 생성 불가능 (필터 조건 위반)'}")

    if not can_generate:
        print("-" * 65)
        print(" ⚠️ 로또봇 추출 대상에서 제외된 사유:")
        for idx, reason in enumerate(eval_info["reasons"], 1):
            print(f"   {idx}. {reason}")
        print("-" * 65)
        print("💡 결과 해석: 이 회차의 1등 번호는 로또봇의 안전 필터 규칙에 의해 사전 차단되므로,")
        print("   로또봇을 무한히 돌려도 해당 조합은 추천 생성되지 않습니다.")
        print("=" * 65)
        return

    print("-" * 65)
    print(" 🔄 1등 당첨 조합이 나올 때까지 시뮬레이션 시도 구동 중...")

    res = simulator.simulate_attempts_for_target(target_drw_no)

    if res.get("found"):
        print("\n" + "=" * 65)
        print(f" 🎉 [{target_drw_no}회차] 1등 조합 포착 성공!")
        print("=" * 65)
        print(f"• 목표 1등 번호   : {res['winning_nums']}")
        print(f"• 도달 시도 횟수   : {res['attempts']:,} 회 (게임)")
        print(f"• 가상 구매 비용   : {res['virtual_cost_krw']:,} 원")
        print(f"• 시뮬레이션 소요시간 : {res['elapsed_sec']} 초")
        print("=" * 65)
    else:
        print(f"\n❌ {res.get('message')}")


def main():
    parser = argparse.ArgumentParser(description="로또 번호 추천 알고리즘 백테스팅 및 특정회차 GUI 시뮬레이터")
    parser.add_argument('--gui', action='store_true', help='Tkinter GUI 화면 실행')
    parser.add_argument('--target-drw', type=int, default=0, help='특정 회차 생성 가능 여부 및 시도 횟수 테스트')
    parser.add_argument('--start-drw', type=int, default=1, help='시작 회차 (기본값: 1)')
    parser.add_argument('--end-drw', type=int, default=0, help='종료 회차 (기본값: 최신 회차)')
    parser.add_argument('--games-per-round', type=int, default=15, help='회차당 생성 게임 수 (기본값: 15)')
    parser.add_argument('--no-filter', action='store_true', help='필터링 미적용 (순수 무작위 추출)')
    parser.add_argument('--trials', type=int, default=1, help='시뮬레이션 반복 횟수 (기본값: 1)')
    parser.add_argument('--compare', action='store_true', help='필터 적용 VS 미적용 비교 리포트 출력')

    args = parser.parse_args()

    # GUI 실행 요청
    if args.gui:
        if not HAS_TKINTER:
            print("❌ Tkinter 모듈을 불러올 수 없어 GUI 모드를 실행하지 못합니다.")
            return
        root = tk.Tk()
        app = LottoSimulatorGUI(root)
        root.mainloop()
        return

    simulator = LottoSimulator()
    if not simulator.history:
        print("❌ lotto_history.csv 파일이 없거나 비어 있습니다.")
        return

    max_drw = max(simulator.history.keys())

    if args.target_drw > 0:
        print_target_analysis_report(simulator, args.target_drw)
        return

    if args.start_drw == 1 and args.end_drw == 0 and not args.compare:
        print("=" * 60)
        print(" 🎰 로또봇 백테스팅 & 시뮬레이터 프로그램")
        print("=" * 60)
        print(" 1. Tkinter GUI 화면으로 실행하기")
        print(" 2. 특정 회차 1등 번호 생성 가능 여부 & 출현 시도 횟수 테스트")
        print(" 3. 필터 적용 vs 미적용 비교 백테스팅")
        print("=" * 60)
        sel = input("선택 (1/2/3): ").strip()

        if sel == '1':
            if HAS_TKINTER:
                root = tk.Tk()
                app = LottoSimulatorGUI(root)
                root.mainloop()
            else:
                print("❌ GUI 환경이 지원되지 않습니다.")
            return
        elif sel == '2':
            drw_str = input(f"테스트할 회차 입력 (1 ~ {max_drw}): ").strip()
            if drw_str.isdigit():
                print_target_analysis_report(simulator, int(drw_str))
            else:
                print("❌ 유효한 회차 번호를 입력해주세요.")
            return
        elif sel == '3':
            args.compare = True

    start_drw = args.start_drw
    end_drw = args.end_drw if args.end_drw > 0 else max_drw

    if args.compare:
        res_filtered = simulator.run_simulation(start_drw, end_drw, args.games_per_round, True, args.trials)
        res_unfiltered = simulator.run_simulation(start_drw, end_drw, args.games_per_round, False, args.trials)

        def display_cli_report(res, title):
            if "error" in res:
                print(f"❌ 오류: {res['error']}")
                return
            print("=" * 60)
            print(f" 📊 {title}")
            print("=" * 60)
            print(f"• 구매 게임 수 : {res['total_games']:,} 게임 | 총 투자금 : {res['total_cost']:,} 원")
            print(f"• 총 당첨 금액 : {res['total_prize']:,} 원 | 수익률 (ROI) : {res['roi']:.2f}%")
            print(f"• 등수 집계     : 1등:{res['rank_counts'][1]} / 2등:{res['rank_counts'][2]} / 3등:{res['rank_counts'][3]} / 4등:{res['rank_counts'][4]} / 5등:{res['rank_counts'][5]}")
            print("=" * 60)

        display_cli_report(res_filtered, "필터 적용 (전략 ON) 백테스팅 결과")
        print("\n")
        display_cli_report(res_unfiltered, "필터 미적용 (전략 OFF / 순수 랜덤) 백테스팅 결과")


if __name__ == "__main__":
    main()
