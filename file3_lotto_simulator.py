import csv
import os
import random
import argparse
from typing import Dict, List, Set, Tuple, Any

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


def check_filters(numbers: List[int]) -> bool:
    """번호 조합 필터링 검증 (file2_lotto_service.py 동일 로직)"""
    # 1. 3연속 이상 번호 제외 (연속 인접 차이 1이 2회 이상 발생 시 3연속 이상)
    consecutive_cnt = 0
    for i in range(len(numbers) - 1):
        if numbers[i + 1] - numbers[i] == 1:
            consecutive_cnt += 1
            if consecutive_cnt >= 2:
                return False
        else:
            consecutive_cnt = 0

    # 2. 총합 범위 (100 ~ 180)
    if not (100 <= sum(numbers) <= 180):
        return False

    # 3. 고유 차이값 개수 조건
    diffs = set()
    for i in range(6):
        for j in range(i + 1, 6):
            diffs.add(numbers[j] - numbers[i])
    if (len(diffs) - 5) < 7:
        return False

    return True


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

    def generate_numbers_for_round(self, target_drw_no: int, history_set_before_target: Set[Tuple[int, ...]],
                                   count: int = 15, use_filter: bool = True) -> List[List[int]]:
        """
        특정 회차(target_drw_no) 시점 기준 번호 생성.
        target_drw_no 미만의 과거 당첨 번호만 history_set_before_target으로 전달받아 미래 정보 유출 차단.
        """
        results = []
        attempts = 0
        max_attempts = 100_000

        while len(results) < count and attempts < max_attempts:
            attempts += 1
            candidate = sorted(random.sample(range(1, 46), 6))

            # 과거 당첨 번호 재출현 제외
            if tuple(candidate) in history_set_before_target:
                continue

            # 필터 조건
            if use_filter and not check_filters(candidate):
                continue

            results.append(candidate)

        return results

    def run_simulation(self, start_drw: int, end_drw: int, games_per_round: int = 15,
                       use_filter: bool = True, trials: int = 1) -> Dict[str, Any]:
        """
        [start_drw ~ end_drw] 구간에 대해 시뮬레이션을 수행하고 결과를 집계
        """
        available_drws = [d for d in range(start_drw, end_drw + 1) if d in self.history]
        if not available_drws:
            return {"error": "지정한 회차 구간의 당첨 데이터가 존재하지 않습니다."}

        total_games = 0
        total_cost = 0
        total_prize = 0
        rank_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 7: 0}

        for trial in range(trials):
            for drw_no in available_drws:
                # 미래 데이터 유출 방지: drw_no 미만의 역대 당첨 조합만 집합으로 구성
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


def print_report(res: Dict[str, Any], title: str = "시뮬레이션 결과"):
    if "error" in res:
        print(f"❌ 오류: {res['error']}")
        return

    print("=" * 60)
    print(f" 📊 {title}")
    print("=" * 60)
    print(f"• 테스트 회차 구간 : {res['start_drw']}회 ~ {res['end_drw']}회 (총 {res['simulated_rounds']}회차)")
    print(f"• 회차당 게임 수   : {res['games_per_round']}게임 (반복 시행: {res['trials']}회)")
    print(f"• 필터 적용 여부   : {'적용 (필터ON)' if res['use_filter'] else '미적용 (순수 랜덤/필터OFF)'}")
    print(f"• 총 구매 게임 수 : {res['total_games']:,} 게임")
    print(f"• 총 투자 금액     : {res['total_cost']:,} 원")
    print(f"• 총 당첨 금액     : {res['total_prize']:,} 원")
    print(f"• 손익 (수익금)    : {res['profit']:,} 원")
    print(f"• 수익률 (ROI)     : {res['roi']:.2f}%")
    print("-" * 60)
    print(" 🏆 당첨 등수 집계")
    print("-" * 60)
    rc = res['rank_counts']
    total = res['total_games']
    print(f"  1등 (6개 일치)     : {rc[1]:>6,} 건 ({(rc[1]/total*100):.4f}%)")
    print(f"  2등 (5개+보너스)   : {rc[2]:>6,} 건 ({(rc[2]/total*100):.4f}%)")
    print(f"  3등 (5개 일치)     : {rc[3]:>6,} 건 ({(rc[3]/total*100):.4f}%)")
    print(f"  4등 (4개 일치)     : {rc[4]:>6,} 건 ({(rc[4]/total*100):.4f}%)")
    print(f"  5등 (3개 일치)     : {rc[5]:>6,} 건 ({(rc[5]/total*100):.4f}%)")
    print(f"  낙첨 (2개 이하)    : {rc[7]:>6,} 건 ({(rc[7]/total*100):.4f}%)")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="로또 번호 추천 알고리즘 백테스팅 및 시뮬레이터")
    parser.add_argument('--start-drw', type=int, default=1, help='시작 회차 (기본값: 1)')
    parser.add_argument('--end-drw', type=int, default=0, help='종료 회차 (기본값: 최신 회차)')
    parser.add_argument('--games-per-round', type=int, default=15, help='회차당 생성 게임 수 (기본값: 15)')
    parser.add_argument('--no-filter', action='store_true', help='필터링 미적용 (순수 무작위 추출)')
    parser.add_argument('--trials', type=int, default=1, help='시뮬레이션 반복 횟수 (기본값: 1)')
    parser.add_argument('--compare', action='store_true', help='필터 적용 VS 미적용 비교 리포트 출력')

    args = parser.parse_args()

    simulator = LottoSimulator()
    if not simulator.history:
        print("❌ lotto_history.csv 파일이 없거나 비어 있습니다.")
        return

    max_drw = max(simulator.history.keys())
    start_drw = args.start_drw
    end_drw = args.end_drw if args.end_drw > 0 else max_drw

    if args.compare:
        print("\n🚀 필터 적용 vs 미적용 비교 시뮬레이션을 시작합니다...\n")
        res_filtered = simulator.run_simulation(
            start_drw=start_drw,
            end_drw=end_drw,
            games_per_round=args.games_per_round,
            use_filter=True,
            trials=args.trials
        )
        res_unfiltered = simulator.run_simulation(
            start_drw=start_drw,
            end_drw=end_drw,
            games_per_round=args.games_per_round,
            use_filter=False,
            trials=args.trials
        )

        print_report(res_filtered, "필터 적용 (전략 ON) 결과")
        print("\n")
        print_report(res_unfiltered, "필터 미적용 (전략 OFF / 순수 랜덤) 결과")
    else:
        use_filter = not args.no_filter
        res = simulator.run_simulation(
            start_drw=start_drw,
            end_drw=end_drw,
            games_per_round=args.games_per_round,
            use_filter=use_filter,
            trials=args.trials
        )
        print_report(res, "로또봇 알고리즘 백테스팅 결과")


if __name__ == "__main__":
    main()
