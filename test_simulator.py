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
        valid_nums = [3, 12, 21, 28, 35, 41]  # 합 140, 3연속 없음
        self.assertTrue(check_filters(valid_nums))

        # 3연속 수 포함 -> False
        invalid_consecutive = [1, 2, 3, 20, 30, 40]
        self.assertFalse(check_filters(invalid_consecutive))

        # 합 범위 이탈 (< 100) -> False
        invalid_sum_low = [1, 2, 3, 4, 5, 6]  # 합 21
        self.assertFalse(check_filters(invalid_sum_low))

        # 합 범위 이탈 (> 180) -> False
        invalid_sum_high = [30, 35, 40, 41, 42, 45]  # 합 233
        self.assertFalse(check_filters(invalid_sum_high))

    def test_is_target_generatable(self):
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, newline='', encoding='utf-8') as tmp:
            writer = csv.writer(tmp)
            writer.writerow(["DrwNo", "N1", "N2", "N3", "N4", "N5", "N6", "Bonus"])
            # 1회차: 정상 필터 통과 조합 (합 140)
            writer.writerow([1, 3, 12, 21, 28, 35, 41, 7])
            # 2회차: 필터 불통과 조합 (3연속 수 포함: 1, 2, 3)
            writer.writerow([2, 1, 2, 3, 20, 30, 40, 9])
            # 3회차: 1회차와 동일 번호 (과거 재출현)
            writer.writerow([3, 3, 12, 21, 28, 35, 41, 10])
            tmp_path = tmp.name

        try:
            sim = LottoSimulator(history_filepath=tmp_path)

            # 1회차: 생성 가능
            can_gen_1, info_1 = sim.is_target_generatable(1)
            self.assertTrue(can_gen_1)

            # 2회차: 필터 불통과로 생성 불가능
            can_gen_2, info_2 = sim.is_target_generatable(2)
            self.assertFalse(can_gen_2)
            self.assertTrue(any("3연속" in r for r in info_2["reasons"]))

            # 3회차: 과거 재출현으로 생성 불가능
            can_gen_3, info_3 = sim.is_target_generatable(3)
            self.assertFalse(can_gen_3)
            self.assertTrue(any("재출현" in r for r in info_3["reasons"]))

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == '__main__':
    unittest.main()
