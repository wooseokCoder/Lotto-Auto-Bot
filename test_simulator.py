import unittest
import tempfile
import os
import csv
from file3_lotto_simulator import check_filters, evaluate_ticket, LottoSimulator

class TestLottoSimulator(unittest.TestCase):

    def test_check_rank(self):
        winning_nums = {1, 10, 20, 30, 40, 45}
        bonus = 7

        # 1등 (6개 일치)
        rank, name, matched, is_bonus = evaluate_ticket([1, 10, 20, 30, 40, 45], winning_nums, bonus)
        self.assertEqual(rank, 1)
        self.assertEqual(matched, 6)

        # 2등 (5개 일치 + 보너스)
        rank, name, matched, is_bonus = evaluate_ticket([1, 10, 20, 30, 40, 7], winning_nums, bonus)
        self.assertEqual(rank, 2)
        self.assertEqual(matched, 5)
        self.assertTrue(is_bonus)

        # 3등 (5개 일치)
        rank, name, matched, is_bonus = evaluate_ticket([1, 10, 20, 30, 40, 41], winning_nums, bonus)
        self.assertEqual(rank, 3)
        self.assertEqual(matched, 5)

        # 4등 (4개 일치)
        rank, name, matched, is_bonus = evaluate_ticket([1, 10, 20, 30, 41, 42], winning_nums, bonus)
        self.assertEqual(rank, 4)
        self.assertEqual(matched, 4)

        # 5등 (3개 일치)
        rank, name, matched, is_bonus = evaluate_ticket([1, 10, 20, 41, 42, 43], winning_nums, bonus)
        self.assertEqual(rank, 5)
        self.assertEqual(matched, 3)

        # 낙첨 (2개 이하)
        rank, name, matched, is_bonus = evaluate_ticket([1, 10, 41, 42, 43, 44], winning_nums, bonus)
        self.assertEqual(rank, 7)
        self.assertEqual(matched, 2)

    def test_check_filters(self):
        # 유효한 조합
        valid_nums = [3, 12, 21, 28, 35, 41] # 합 140, 3연속 없음, diff count 만족
        self.assertTrue(check_filters(valid_nums))

        # 3연속 수 포함 -> False
        invalid_consecutive = [1, 2, 3, 20, 30, 40]
        self.assertFalse(check_filters(invalid_consecutive))

        # 합 범위 이탈 (< 100) -> False
        invalid_sum_low = [1, 2, 3, 4, 5, 6] # 합 21
        self.assertFalse(check_filters(invalid_sum_low))

        # 합 범위 이탈 (> 180) -> False
        invalid_sum_high = [30, 35, 40, 41, 42, 45] # 합 233
        self.assertFalse(check_filters(invalid_sum_high))

    def test_history_isolation(self):
        # 임시 csv 파일 생성하여 회차별 과거 내역 분리 검증
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, newline='', encoding='utf-8') as tmp:
            writer = csv.writer(tmp)
            writer.writerow(["DrwNo", "N1", "N2", "N3", "N4", "N5", "N6", "Bonus"])
            writer.writerow([1, 10, 20, 30, 40, 41, 42, 7])
            writer.writerow([2, 1, 2, 3, 4, 5, 6, 7])
            tmp_path = tmp.name

        try:
            sim = LottoSimulator(history_filepath=tmp_path)
            self.assertEqual(len(sim.history), 2)

            # round 2 생성 시 round 1 이전 과거 집합에 round 1 당첨 조합 포함
            past_set_for_round_2 = {sim.history[1]["nums_tuple"]}
            # round 2 당첨 조합 (1,2,3,4,5,6)은 포함되지 않아야 함
            self.assertNotIn((1, 2, 3, 4, 5, 6), past_set_for_round_2)
            self.assertIn((10, 20, 30, 40, 41, 42), past_set_for_round_2)

            # generate_numbers_for_round 검증
            picks = sim.generate_numbers_for_round(
                target_drw_no=2,
                history_set_before_target=past_set_for_round_2,
                count=10,
                use_filter=False
            )
            for p in picks:
                self.assertNotEqual(tuple(p), (10, 20, 30, 40, 41, 42))

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

if __name__ == '__main__':
    unittest.main()
