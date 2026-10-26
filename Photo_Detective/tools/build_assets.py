"""DEVELOPER TOOL - NOT NEEDED TO PLAY THE GAME.

Builds every picture in assets/ and writes data/cases.json. The finished
PNG files are already included, so the tutor does not need to run this.
It is the only file in the project that uses an external library (Pillow),
and the game itself never imports it.

What it does:
  1. (optional) Imports original photos from tools/source_photos/,
     crops them to 4:3 and saves 640 x 480 references in assets/references/.
     Skipped when that folder is missing - the references are already there.
  2. Makes the candidate pictures for each difficulty level:
       Easy / Medium  a lightly edited copy + three other scenes
       Hard           copies with OBVIOUS edits (mirrored, black and white,
                      cropped to a wider 640 x 360 shape)
       Very Hard      copies with NOTICEABLE edits (darker, duller,
                      slightly zoomed)
       Expert         copies with one small LOCAL edit each (one object
                      recoloured) - find them with the flicker test
  3. Scores every case with the game's own maths (game_engine.compare) and
     stops if the intended answer is not the clear winner.

Run from the project folder (only if you want to rebuild the art):
    python -m pip install pillow pillow-heif
    python tools/build_assets.py
"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game_engine import compare  # noqa: E402  (the game's own scoring)
from image_tools import PixelGrid  # noqa: E402

SOURCE_DIR = ROOT / "tools" / "source_photos"
REFERENCE_DIR = ROOT / "assets" / "references"
MATCH_DIR = ROOT / "assets" / "matches"
VARIANT_DIR = ROOT / "assets" / "variants"
SIZE = (640, 480)
CLUE = "Which candidate is the closest match to the reference image?"
LABELS = {1: "Easy", 2: "Medium", 3: "Hard", 4: "Very Hard", 5: "Expert"}

# slug: (title, horizontal focus, vertical focus) - focus picks the 4:3 crop.
PHOTOS = {
    "koala": ("Sleepy Koala", 0.5, 0.45),
    "tram": ("George Street Light Rail", 0.5, 0.5),
    "mountains": ("The Three Sisters", 0.5, 0.5),
    "wallaby": ("Wallaby in the Shade", 0.5, 0.62),
    "ferry": ("Ferry at Circular Quay", 0.5, 0.5),
    "quad": ("The Quadrangle", 0.5, 0.5),
    "opera": ("Opera House at Dusk", 0.5, 0.5),
    "bondi": ("Bondi Icebergs", 0.5, 0.5),
    "cockatoo": ("Cockatoo Lookout", 0.5, 0.5),
    "cafe": ("Sydney Brunch", 0.5, 0.5),
    "dog": ("The Flower Collar", 0.5, 0.5),
    "giraffe": ("Lunch with a View", 0.5, 0.36),
}

# Easy: three unrelated scenes. Medium: at least one similar scene.
SCENE_CASES = {
    "koala": (1, ["tram", "cafe", "bondi"]),
    "tram": (1, ["dog", "mountains", "cafe"]),
    "mountains": (1, ["cafe", "tram", "opera"]),
    "wallaby": (2, ["koala", "dog", "quad"]),
    "ferry": (2, ["opera", "cockatoo", "tram"]),
    "quad": (2, ["tram", "opera", "cafe"]),
}

# Hard and Very Hard: whole-picture edits of the reference itself.
GLOBAL_EDIT_CASES = {"opera": 3, "bondi": 3, "cockatoo": 4, "cafe": 4}

# Expert: (description, (kind, box, hue range in degrees, hue shift, minimum
# saturation)) - boxes are (left, top, right, bottom) on the 640 x 480 picture.
# Each edit must be big enough for the 64 x 64 scoring grid to notice it.
LOCAL_EDITS = {
    "dog": [
        ("flower turned blue", ("recolour", (326, 264, 396, 326), (0, 45), 200, 40)),
        ("bright leaves turned orange", ("recolour", (520, 70, 640, 250), (55, 110), -50, 60)),
        ("one fence board turned green", ("recolour", (484, 190, 560, 400), (150, 200), -80, 25)),
    ],
    "giraffe": [
        ("basket turned green", ("recolour", (75, 290, 150, 385), (10, 50), 60, 60)),
        ("yellow flowers turned pink", ("recolour", (0, 150, 70, 440), (40, 70), -85, 60)),
        ("lamp post turned blue", ("recolour", (36, 24, 108, 480), (0, 40), 190, 40)),
    ],
}


# ---------------------------------------------------------------- importing

def open_photo(path):
    if path.suffix.lower() in (".heic", ".heif"):
        import pillow_heif  # only needed for iPhone photos
        pillow_heif.register_heif_opener()
    return ImageOps.exif_transpose(Image.open(path)).convert("RGB")


def import_photos():
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    for slug, (_title, focus_x, focus_y) in PHOTOS.items():
        matches = list(SOURCE_DIR.glob(f"{slug}.*"))
        if not matches:
            raise FileNotFoundError(f"No source photo named {slug}.* in {SOURCE_DIR}")
        image = open_photo(matches[0])
        width, height = image.size
        if width / height > 4 / 3:
            crop_w, crop_h = round(height * 4 / 3), height
        else:
            crop_w, crop_h = width, round(width * 3 / 4)
        left = min(max(0, round(width * focus_x - crop_w / 2)), width - crop_w)
        top = min(max(0, round(height * focus_y - crop_h / 2)), height - crop_h)
        image = image.crop((left, top, left + crop_w, top + crop_h)).resize(SIZE, Image.LANCZOS)
        image.save(REFERENCE_DIR / f"{slug}.png", optimize=True)
        print(f"imported {matches[0].name} -> references/{slug}.png")


# -------------------------------------------------------------------- edits

def light_edit(image, brightness=0.96, colour=1.04):
    """The 'closest match': a gentle tone change the eye barely notices."""
    image = ImageEnhance.Brightness(image).enhance(brightness)
    return ImageEnhance.Color(image).enhance(colour)


def zoom(image, amount):
    width, height = image.size
    dx, dy = round(width * amount / 2), round(height * amount / 2)
    return image.crop((dx, dy, width - dx, height - dy)).resize(image.size, Image.LANCZOS)


def widen(image, amount):
    """Cut amount/2 off the top and the bottom WITHOUT resizing back, so the
    saved picture really has a wider shape (640 x 480 -> 640 x 360 for 0.25).
    This is the edit that the aspect-ratio measure detects."""
    width, height = image.size
    dy = round(height * amount / 2)
    return image.crop((0, dy, width, height - dy))


def recolour(image, box, hue_range, shift, min_saturation=60):
    """Rotate by `shift` degrees the hue of strongly coloured pixels in box
    whose hue (0-360 degrees) lies in hue_range."""
    image = image.copy()
    region = image.crop(box)
    hsv = region.convert("HSV")
    hue, sat, val = hsv.split()
    low, high = hue_range
    hue_pixels, sat_pixels = hue.load(), sat.load()
    mask = Image.new("L", region.size, 0)
    mask_pixels = mask.load()
    for y in range(region.height):
        for x in range(region.width):
            degrees = hue_pixels[x, y] * 360 / 255
            if low <= degrees <= high and sat_pixels[x, y] >= min_saturation:
                hue_pixels[x, y] = int(hue_pixels[x, y] + shift * 255 / 360) % 256
                mask_pixels[x, y] = 255
    changed = Image.merge("HSV", (hue, sat, val)).convert("RGB")
    mask = mask.filter(ImageFilter.GaussianBlur(1.2))
    image.paste(changed, box[:2], mask)
    return image


def apply_local(image, edit):
    kind, box, hue_range, shift, min_saturation = edit
    return recolour(image, box, hue_range, shift, min_saturation)


# ------------------------------------------------------------------ building

def save(image, folder, name):
    folder.mkdir(parents=True, exist_ok=True)
    image.save(folder / name, optimize=True)
    return f"assets/{folder.name}/{name}"


def build_cases():
    references = {slug: Image.open(REFERENCE_DIR / f"{slug}.png").convert("RGB")
                  for slug in PHOTOS}
    cases = []
    for slug, (title, _fx, _fy) in PHOTOS.items():
        reference = references[slug]
        if slug in SCENE_CASES:
            difficulty, others = SCENE_CASES[slug]
            candidates = [{"path": save(light_edit(reference), MATCH_DIR, f"{slug}_match.png"),
                           "kind": "closest match", "change": "tiny tone change"}]
            for other in others:
                candidates.append({"path": f"assets/references/{other}.png",
                                   "kind": "distractor", "change": "a different scene"})
        elif slug in GLOBAL_EDIT_CASES:
            difficulty = GLOBAL_EDIT_CASES[slug]
            if difficulty == 3:
                edits = [("mirrored left to right", ImageOps.mirror(reference)),
                         ("black and white", ImageOps.grayscale(reference).convert("RGB")),
                         ("cropped to a wider shape", widen(reference, 0.25))]
            else:
                edits = [("darker", ImageEnhance.Brightness(reference).enhance(0.80)),
                         ("much less colourful", ImageEnhance.Color(reference).enhance(0.30)),
                         ("slightly zoomed in", zoom(reference, 0.10))]
            candidates = [{"path": save(light_edit(reference, 0.99, 1.01), VARIANT_DIR,
                                        f"{slug}_match.png"),
                           "kind": "closest match", "change": "tiny tone change"}]
            for number, (change, edited) in enumerate(edits, start=1):
                candidates.append({"path": save(edited, VARIANT_DIR, f"{slug}_edit{number}.png"),
                                   "kind": "distractor", "change": change})
        else:
            difficulty = 5
            # The real match is the untouched photo: it does not move at all
            # in the flicker test, while every distractor changes somewhere.
            candidates = [{"path": f"assets/references/{slug}.png",
                           "kind": "closest match", "change": "untouched copy"}]
            for number, (change, edit) in enumerate(LOCAL_EDITS[slug], start=1):
                candidates.append({"path": save(apply_local(reference, edit), VARIANT_DIR,
                                                f"{slug}_edit{number}.png"),
                                   "kind": "distractor", "change": change})
        cases.append({
            "id": slug, "title": title, "clue": CLUE,
            "difficulty": difficulty, "difficulty_label": LABELS[difficulty],
            "reference": f"assets/references/{slug}.png", "candidates": candidates,
        })
    return sorted(cases, key=lambda case: case["difficulty"])


# ---------------------------------------------------------------- checking

def grid_of(path):
    image = Image.open(ROOT / path).convert("RGB")
    return PixelGrid.from_ppm(image.width, image.height, image.tobytes())


MINIMUM_MARGIN = {1: 8.0, 2: 4.0, 3: 1.0, 4: 0.5, 5: 0.05}


def check(cases):
    """Score every case with the game's own maths and print a report."""
    print(f"\n{'case':12s} {'level':10s} {'match':>6s} {'next':>6s} {'margin':>7s}")
    for case in cases:
        reference = grid_of(case["reference"])
        scored = sorted(((compare(reference, grid_of(c["path"]))["overall"], c)
                         for c in case["candidates"]), key=lambda item: -item[0])
        (best, winner), (second, _) = scored[0], scored[1]
        margin = best - second
        print(f"{case['id']:12s} {case['difficulty_label']:10s} {best:6.2f} {second:6.2f} {margin:7.2f}")
        for score, candidate in scored[1:]:
            print(f"{'':24s}{score:6.2f}  {candidate['change']}")
        if winner["kind"] != "closest match":
            raise SystemExit(f"FAILED: {case['id']} - a distractor scored highest")
        if margin < MINIMUM_MARGIN[case["difficulty"]]:
            print(f"  warning: margin below {MINIMUM_MARGIN[case['difficulty']]} for this level")


def main():
    if SOURCE_DIR.exists():
        import_photos()
    for folder in (MATCH_DIR, VARIANT_DIR):
        for old in folder.glob("*.png"):
            old.unlink()
    cases = build_cases()
    with open(ROOT / "data" / "cases.json", "w", encoding="utf-8") as file:
        json.dump(cases, file, indent=2)
    check(cases)
    print(f"\nWrote {len(cases)} cases to data/cases.json")


if __name__ == "__main__":
    main()
