import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from training.common import ranking_metrics, split_resume_ids, weak_label


class TrainingPipelineTests(unittest.TestCase):
    def test_resume_splits_do_not_leak(self):
        splits = split_resume_ids([f"r{i}" for i in range(100)], seed=42)
        self.assertFalse(splits["train"] & splits["validation"])
        self.assertFalse(splits["train"] & splits["test"])
        self.assertFalse(splits["validation"] & splits["test"])
        self.assertEqual(sum(map(len, splits.values())), 100)

    def test_weak_label_thresholds(self):
        required = ["Python", "AWS", "Docker", "SQL"]
        self.assertEqual(weak_label([], required)[0], 0)
        self.assertEqual(weak_label(["Python"], required)[0], 2)
        self.assertEqual(weak_label(["Python", "AWS"], required)[0], 3)

    def test_perfect_ranking_metrics(self):
        rows = [
            {"jd_id": "jd", "label": 3, "score": 0.9},
            {"jd_id": "jd", "label": 2, "score": 0.8},
            {"jd_id": "jd", "label": 0, "score": 0.1},
        ]
        metrics = ranking_metrics(rows, "score")
        self.assertAlmostEqual(metrics["precision_at_3"], 2 / 3, places=4)
        self.assertEqual(metrics["recall_at_5"], 1.0)
        self.assertEqual(metrics["ndcg_at_5"], 1.0)
        self.assertEqual(metrics["mrr"], 1.0)


if __name__ == "__main__":
    unittest.main()
