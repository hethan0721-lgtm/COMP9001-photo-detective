"""Window tests - need a desktop and Python with Tk 8.6. Skipped automatically
when no window can be opened (for example on Ed).

Run from the project folder:   python -m unittest discover -s tests -v
"""

import random
import sys
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from game_engine import load_cases, prepare_round  # noqa: E402
from image_tools import ImageLibrary  # noqa: E402


class WindowTestCase(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("no desktop available to open a window")
        if tk.TkVersion < 8.6:
            self.root.destroy()
            self.skipTest("Tk 8.6 or newer is needed to read PNG files")
        self.root.withdraw()

    def tearDown(self):
        self.root.destroy()


class RealImageTests(WindowTestCase):
    def test_every_case_has_one_clear_winner(self):
        images = ImageLibrary(self.root)
        for case in load_cases():
            result = prepare_round(case, images.grid, random.Random(0))
            best = result["candidates"][result["best_index"]]
            self.assertEqual(best["kind"], "closest match", case["id"])
            self.assertGreater(result["margin"], 0, case["id"])

    def test_pictures_are_scaled_to_fit(self):
        images = ImageLibrary(self.root)
        path = PROJECT_DIR / load_cases()[0]["reference"]
        photo = images.fitted(path, 300, 300)
        self.assertLessEqual(photo.width(), 300)
        self.assertLessEqual(photo.height(), 300)


class FullGameTests(WindowTestCase):
    def test_play_a_perfect_game(self):
        import main
        # Keep the real data/scores.txt untouched while testing.
        with mock.patch.object(main, "save_score") as fake_save, \
                mock.patch.object(main, "load_high_score", return_value=0):
            app = main.PhotoDetectiveApp(self.root)
            app.start_game()
            for _ in range(5):
                self.assertEqual(app.screen, "game")
                app.select_candidate(app.current_case["best_index"])
                app.next_round()
            self.assertEqual(app.screen, "result")
            self.assertEqual(app.score, 500)
            fake_save.assert_called_once_with(500, 5, 5)


if __name__ == "__main__":
    unittest.main()
