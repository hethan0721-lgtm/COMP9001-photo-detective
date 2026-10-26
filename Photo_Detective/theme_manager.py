"""Loads the colour palette from theme.json, with safe built-in defaults.

Edit theme.json in any text editor to recolour the game. Missing or
invalid values fall back to the defaults below, so a typo never stops the
game from starting.
"""

import json
from pathlib import Path

THEME_PATH = Path(__file__).resolve().parent / "theme.json"

DEFAULT_THEME = {
    "desk": "#18222C",          # dark background ("the detective's desk")
    "desk_light": "#22303C",
    "paper": "#F8F3E7",         # polaroid frames and cards
    "folder": "#EAD5A8",        # manila case-file folder
    "folder_dark": "#D2B47C",
    "cork": "#B7854F",
    "cork_dark": "#94683A",
    "ink": "#1F2A33",           # text on paper
    "ink_soft": "#6E6455",
    "on_desk": "#F4EBDD",       # text on the dark desk
    "on_desk_soft": "#93A1AD",
    "accent": "#E0533A",        # red string, stamps and main buttons
    "accent_dark": "#A93A27",
    "amber": "#F2B544",
    "amber_ink": "#B27413",     # amber dark enough for text on paper
    "success": "#2F9E6A",
    "danger": "#D64545",
    "window_width": 1280,
    "window_height": 820,
}


def load_theme(path=THEME_PATH):
    """Return a complete theme dictionary, falling back safely if needed."""
    theme = dict(DEFAULT_THEME)
    try:
        with open(path, "r", encoding="utf-8") as file:
            stored = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return theme
    if not isinstance(stored, dict):
        return theme
    for key, default in DEFAULT_THEME.items():
        value = stored.get(key)
        if isinstance(default, str) and isinstance(value, str) and value.startswith("#"):
            theme[key] = value
        elif isinstance(default, int) and isinstance(value, int) and value > 0:
            theme[key] = value
    return theme
