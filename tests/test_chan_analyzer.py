import unittest

from app.chan_analyzer import analyze_confirmed_pens, build_candidate_pens, find_fractals
from app.models import KLine, Pen


def sample_klines():
    prices = [
        (10, 11, 9, 10),
        (10, 12, 10, 11),
        (11, 15, 12, 14),
        (14, 13, 10, 11),
        (11, 10, 7, 8),
        (8, 9, 8, 9),
        (9, 13, 10, 12),
        (12, 16, 13, 15),
        (15, 14, 10, 11),
        (11, 10, 6, 7),
        (7, 8, 7, 8),
        (8, 12, 9, 11),
        (11, 17, 13, 16),
    ]
    return [
        KLine("sh000852", f"2026-01-01 {index:02d}:00", open_, high, low, close)
        for index, (open_, high, low, close) in enumerate(prices)
    ]


class ChanAnalyzerTest(unittest.TestCase):
    def test_find_fractals(self):
        fractals = find_fractals(sample_klines())
        self.assertGreaterEqual(len(fractals), 2)
        self.assertEqual(fractals[0].kind, "top")

    def test_build_candidate_pens(self):
        pens = build_candidate_pens(sample_klines(), min_gap=2)
        self.assertGreaterEqual(len(pens), 2)
        self.assertTrue(all(pen.status == "candidate" for pen in pens))

    def test_only_confirmed_pens_are_analyzed(self):
        pens = [
            Pen(None, "sh000852", "confirmed", "manual", "1", "2", 10, 15, "up"),
            Pen(None, "sh000852", "candidate", "auto", "2", "3", 15, 9, "down"),
            Pen(None, "sh000852", "confirmed", "manual", "3", "4", 9, 14, "up"),
            Pen(None, "sh000852", "confirmed", "manual", "4", "5", 14, 8, "down"),
        ]
        result = analyze_confirmed_pens(pens)
        self.assertEqual(len(result["segments"]), 1)
        self.assertEqual(result["signals"], [])


if __name__ == "__main__":
    unittest.main()
