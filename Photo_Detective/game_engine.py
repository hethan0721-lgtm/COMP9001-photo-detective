"""Game data, similarity scoring, and score history.

Pictures arrive as PixelGrid objects from image_tools.py: 3-D lists shaped
grid.rows[row][column][channel]. Every similarity measure below is
calculated by hand with nested loops - no image library is used.
"""

import json
import math
import random
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
CASE_PATH = PROJECT_DIR / "data" / "cases.json"
SCORE_PATH = PROJECT_DIR / "data" / "scores.txt"

# How much each clue counts towards the overall similarity (adds up to 1.0).
WEIGHTS = {"pixel": 0.40, "colour": 0.25, "brightness": 0.20, "aspect_ratio": 0.15}


# ----------------------------------------------------------------- case data

def load_cases(path=CASE_PATH):
    """Read and check the case file (JSON)."""
    try:
        with open(path, "r", encoding="utf-8") as file:
            cases = json.load(file)
    except FileNotFoundError:
        raise FileNotFoundError(f"Case file not found: {path}") from None
    except json.JSONDecodeError as error:
        raise ValueError(f"Case file is not valid JSON: {error}") from None
    if not isinstance(cases, list) or not cases:
        raise ValueError("The case file does not contain any cases.")
    return cases


def choose_cases(cases, count=5, rng=None):
    """Choose one random case from each difficulty, in increasing order."""
    if count != 5:
        raise ValueError("Photo Detective games must contain five cases.")
    random_source = rng if rng is not None else random
    chosen = []
    for difficulty in range(1, 6):
        choices = [case for case in cases if case.get("difficulty") == difficulty]
        if not choices:
            raise ValueError(f"No cases are available for difficulty {difficulty}.")
        chosen.append(random_source.choice(choices))
    return chosen


# ----------------------------------------------------------- similarity maths

def mean_colour(grid):
    """Average [r, g, b] over every cell of the grid."""
    totals = [0.0, 0.0, 0.0]
    cell_count = 0
    for row in grid.rows:
        for cell in row:
            for channel in range(3):
                totals[channel] += cell[channel]
            cell_count += 1
    return [total / cell_count for total in totals]


def brightness(grid):
    """Average perceived brightness (0-255) using the standard luma weights."""
    red, green, blue = mean_colour(grid)
    return 0.299 * red + 0.587 * green + 0.114 * blue


def pixel_similarity(reference, candidate):
    """Compare the two grids cell by cell and channel by channel."""
    total_difference = 0.0
    values_compared = 0
    for row_index in range(len(reference.rows)):
        for column_index in range(len(reference.rows[row_index])):
            reference_cell = reference.rows[row_index][column_index]
            candidate_cell = candidate.rows[row_index][column_index]
            for channel in range(3):
                total_difference += abs(reference_cell[channel] - candidate_cell[channel])
                values_compared += 1
    average_difference = total_difference / values_compared
    return 100 * (1 - average_difference / 255)


def colour_similarity(reference, candidate):
    distance = math.dist(mean_colour(reference), mean_colour(candidate))
    largest_possible = math.sqrt(3 * 255 ** 2)
    return 100 * (1 - distance / largest_possible)


def brightness_similarity(reference, candidate):
    return 100 * (1 - abs(brightness(reference) - brightness(candidate)) / 255)


def aspect_ratio_similarity(reference, candidate):
    small = min(reference.aspect_ratio, candidate.aspect_ratio)
    large = max(reference.aspect_ratio, candidate.aspect_ratio)
    return 100 * small / large


def compare(reference, candidate):
    """Return the four clue scores plus the weighted overall score (0-100)."""
    scores = {
        "pixel": pixel_similarity(reference, candidate),
        "colour": colour_similarity(reference, candidate),
        "brightness": brightness_similarity(reference, candidate),
        "aspect_ratio": aspect_ratio_similarity(reference, candidate),
    }
    scores = {name: max(0.0, min(100.0, value)) for name, value in scores.items()}
    scores["overall"] = sum(scores[name] * weight for name, weight in WEIGHTS.items())
    return scores


# --------------------------------------------------------------- one round

def prepare_round(case, grid_for, rng=None):
    """Resolve paths, score and shuffle the four candidates of one case.

    grid_for turns an image path into a PixelGrid. The game passes
    ImageLibrary.grid; tests can pass a fake function instead.
    """
    random_source = rng if rng is not None else random
    if len(case["candidates"]) != 4:
        raise ValueError(f"Case {case['id']} must contain exactly four candidates.")
    reference_path = PROJECT_DIR / case["reference"]
    reference_grid = grid_for(reference_path)

    candidates = []
    for candidate in case["candidates"]:
        item = candidate.copy()
        item["path"] = PROJECT_DIR / item["path"]
        item["scores"] = compare(reference_grid, grid_for(item["path"]))
        candidates.append(item)
    random_source.shuffle(candidates)

    ranking = sorted(range(4), key=lambda i: candidates[i]["scores"]["overall"], reverse=True)
    best_index = ranking[0]
    if candidates[best_index].get("kind") != "closest match":
        raise ValueError(f"Case {case['id']}: the highest score is not the marked match.")

    return {
        "id": case["id"],
        "title": case["title"],
        "clue": case["clue"],
        "difficulty": case["difficulty"],
        "difficulty_label": case["difficulty_label"],
        "reference": reference_path,
        "candidates": candidates,
        "best_index": best_index,
        "margin": (candidates[best_index]["scores"]["overall"]
                   - candidates[ranking[1]]["scores"]["overall"]),
    }


# ------------------------------------------------------------ score history

def save_score(score, correct, total, path=SCORE_PATH):
    """Append one compact history line using file I/O."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as file:
            file.write(f"{score},{correct},{total}\n")
    except OSError:
        return False  # the game still finishes; the score is just not saved
    return True


def load_high_score(path=SCORE_PATH):
    """Return the best score in the history file; damaged lines are skipped."""
    best = 0
    try:
        with open(path, "r", encoding="utf-8") as file:
            for line in file:
                try:
                    best = max(best, int(line.split(",")[0]))
                except ValueError:
                    continue
    except OSError:
        return 0
    return best


def load_scores(path=SCORE_PATH):
    """Return every saved score, oldest first; damaged lines are skipped."""
    scores = []
    try:
        with open(path, "r", encoding="utf-8") as file:
            for line in file:
                try:
                    scores.append(int(line.split(",")[0]))
                except ValueError:
                    continue
    except OSError:
        return []
    return scores
