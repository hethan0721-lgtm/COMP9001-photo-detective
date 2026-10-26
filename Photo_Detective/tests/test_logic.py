"""Logic tests for Photo Detective - no window needed, so these also run on Ed.

Run from the project folder:   python -m unittest discover -s tests -v
"""

import random
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from game_engine import (  # noqa: E402
    choose_cases, compare, load_cases, load_high_score, mean_colour, save_score,
)
from image_tools import PixelGrid  # noqa: E402
from theme_manager import DEFAULT_THEME, load_theme  # noqa: E402


def solid_grid(colour, width=90, height=60):
    """A tiny fake picture where every cell has the same colour."""
    rows = [[list(colour) for _ in range(4)] for _ in range(4)]
    return PixelGrid(rows, width, height)


class PixelGridTests(unittest.TestCase):
    def test_grid_is_rows_of_cells_of_channels(self):
        # A 2 x 2 picture: red, green / blue, white
        pixels = bytes([255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 255])
        grid = PixelGrid.from_ppm(2, 2, pixels, size=2)
        self.assertEqual(len(grid.rows), 2)
        self.assertEqual(len(grid.rows[0]), 2)
        self.assertEqual(grid.rows[0][0], [255, 0, 0])
        self.assertEqual(grid.rows[1][1], [255, 255, 255])

    def test_aspect_ratio(self):
        self.assertAlmostEqual(solid_grid((0, 0, 0), 900, 600).aspect_ratio, 1.5)


class SimilarityTests(unittest.TestCase):
    def test_identical_pictures_score_100(self):
        grid = solid_grid((120, 80, 40))
        self.assertAlmostEqual(compare(grid, grid)["overall"], 100.0)

    def test_closer_colour_scores_higher(self):
        reference = solid_grid((100, 100, 100))
        close = solid_grid((110, 100, 100))
        far = solid_grid((250, 10, 10))
        self.assertGreater(compare(reference, close)["overall"],
                           compare(reference, far)["overall"])

    def test_black_and_white_are_opposites(self):
        scores = compare(solid_grid((0, 0, 0)), solid_grid((255, 255, 255)))
        self.assertAlmostEqual(scores["pixel"], 0.0)
        self.assertAlmostEqual(scores["brightness"], 0.0)

    def test_different_shape_lowers_ratio_score(self):
        wide = solid_grid((50, 50, 50), 900, 600)
        square = solid_grid((50, 50, 50), 600, 600)
        self.assertLess(compare(wide, square)["aspect_ratio"], 100)

    def test_mean_colour(self):
        self.assertEqual(mean_colour(solid_grid((10, 20, 30))), [10, 20, 30])


class CaseDataTests(unittest.TestCase):
    def test_case_file_is_complete(self):
        cases = load_cases()
        self.assertEqual(len(cases), 12)
        self.assertEqual({case["difficulty"] for case in cases}, {1, 2, 3, 4, 5})
        for case in cases:
            self.assertEqual(len(case["candidates"]), 4, case["id"])
            paths = [case["reference"]] + [c["path"] for c in case["candidates"]]
            for path in paths:
                self.assertTrue(path.endswith(".png"), path)
                self.assertTrue((PROJECT_DIR / path).exists(), path)
            marked = [c for c in case["candidates"] if c["kind"] == "closest match"]
            self.assertEqual(len(marked), 1, case["id"])

    def test_games_go_from_easy_to_expert(self):
        chosen = choose_cases(load_cases(), 5, random.Random(1))
        self.assertEqual([case["difficulty"] for case in chosen], [1, 2, 3, 4, 5])

    def test_broken_case_file_gives_clear_error(self):
        with tempfile.TemporaryDirectory() as folder:
            bad = Path(folder) / "cases.json"
            bad.write_text("{not json", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_cases(bad)


class ScoreHistoryTests(unittest.TestCase):
    def test_save_and_read_back(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "scores.txt"
            self.assertEqual(load_high_score(path), 0)
            save_score(300, 3, 5, path)
            save_score(500, 5, 5, path)
            self.assertEqual(load_high_score(path), 500)

    def test_damaged_lines_are_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "scores.txt"
            path.write_text("garbage\n400,4,5\n", encoding="utf-8")
            self.assertEqual(load_high_score(path), 400)


class ThemeTests(unittest.TestCase):
    def test_missing_theme_file_uses_defaults(self):
        self.assertEqual(load_theme(Path("no_such_theme.json")), DEFAULT_THEME)


if __name__ == "__main__":
    unittest.main()
