# >>> RUN THIS FILE TO PLAY:   python main.py      (Windows: double-click start.bat)
"""Photo Detective - spot the photo that really matches the evidence.

A Tkinter desktop game. Every case shows an evidence photo and four
suspects; the player accuses the suspect they think is the closest match.
The program then reveals its own forensic report: a similarity score for
every suspect, calculated in game_engine.py from the picture's pixels.

Needs only Python 3.8+ with Tkinter (included with the normal installers
from python.org). No pip packages, internet connection or accounts.

Files:
    main.py           this file - the window, drawing and controls
    game_engine.py    cases, similarity maths and score history
    image_tools.py    PNG loading, pixel grids and image resizing
    theme_manager.py  reads the colour palette from theme.json
"""

import math
import random
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox

from game_engine import (
    PROJECT_DIR, choose_cases, load_cases, load_high_score, load_scores, prepare_round,
    save_score,
)
from image_tools import ImageLibrary
from theme_manager import load_theme

CASES_PER_GAME = 5
POINTS_PER_CASE = 100
DIFFICULTY_LABELS = {1: "Easy", 2: "Medium", 3: "Hard", 4: "Very Hard", 5: "Expert"}

# The first installed font in each list is used, so the game looks right on
# Windows, macOS and Linux without shipping any font files.
FONT_CHOICES = {
    "sans": ["Segoe UI", "Helvetica Neue", "Avenir Next", "Arial", "Liberation Sans", "DejaVu Sans"],
    "serif": ["Georgia", "Charter", "Cambria", "Lora", "DejaVu Serif", "Times New Roman"],
    "mono": ["Courier New", "Menlo", "Consolas", "Liberation Mono", "DejaVu Sans Mono", "Courier"],
}
DIFFICULTY_COLOURS = {1: "#4FA3D1", 2: "#2F9E6A", 3: "#E2A930", 4: "#E8793A", 5: "#D64545"}
CLUES = [("pixel", "PIX"), ("colour", "COL"), ("brightness", "LUM"), ("aspect_ratio", "RAT")]
DIFFICULTY_NOTES = {
    1: "The suspects show completely different scenes. Trust your first look.",
    2: "One suspect shows a similar kind of scene. Check the details.",
    3: "All four are copies of the evidence. Three have obvious edits: "
       "flipped, black and white or cropped to a wider shape.",
    4: "All four are copies. Three are darker, duller or slightly zoomed in. "
       "Compare them carefully.",
    5: "Three copies have ONE small object recoloured. Use the flicker test: "
       "the real match never moves.",
}
FLICKER_MS = 420           # how fast the flicker test swaps pictures
SHADOW = "#0D141A"

# Pictures used to decorate the start screen's corkboard.
BOARD_PHOTOS = [
    ("assets/references/opera.png", "EVIDENCE"),
    ("assets/variants/opera_edit1.png", "SUSPECT 1"),
    ("assets/references/koala.png", "SUSPECT 2"),
]


def rank_for(correct):
    """Detective rank for the number of correct answers in one game."""
    if correct == CASES_PER_GAME:
        return "Master Detective"
    if correct >= 4:
        return "Senior Detective"
    if correct >= 2:
        return "Junior Detective"
    return "Rookie Detective"


class PhotoDetectiveApp:
    """Owns the window and moves between the start, game and result screens."""

    def __init__(self, root, rng=None):
        self.root = root
        self.rng = rng or random.Random()
        self.theme = load_theme()
        self.cases = load_cases()
        self.images = ImageLibrary(root)
        # Check every case and picture now, so a broken file is reported at start-up.
        choose_cases(self.cases, CASES_PER_GAME, random.Random(0))
        for case in self.cases:
            prepare_round(case, self.images.grid, random.Random(0))
        self.font_families = self._pick_fonts()
        self._font_cache = {}

        root.title("Photo Detective")
        root.geometry(f"{self.theme['window_width']}x{self.theme['window_height']}")
        root.minsize(1040, 700)
        root.configure(bg=self.theme["desk"])
        self.canvas = tk.Canvas(root, bg=self.theme["desk"], highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<Configure>", self._schedule_redraw)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", lambda _event: self._set_hover(None))
        self.canvas.bind("<Button-1>", self._on_click)
        root.bind("<Key>", self._on_key)

        self.screen = "start"
        self.round_cases = []
        self.round_index = 0
        self.current_case = None
        self.history = []          # one dict per finished case in this game
        self.score = 0
        self.answered = False
        self.selected = None
        self.best_before_game = load_high_score()

        self.card_boxes = []       # screen rectangles of the four suspects
        self.hover_index = None
        self.flicker_job = None
        self.flicker_showing_suspect = False
        self.redraw_job = None
        self.draw()

    # ------------------------------------------------------------ helpers

    def _pick_fonts(self):
        installed = set(tkfont.families(self.root))
        chosen = {}
        for kind, options in FONT_CHOICES.items():
            chosen[kind] = next((name for name in options if name in installed), "TkDefaultFont")
        return chosen

    def font(self, kind, size, weight="normal"):
        return (self.font_families[kind], size, weight)

    def text_width(self, font_spec, text):
        if font_spec not in self._font_cache:
            self._font_cache[font_spec] = tkfont.Font(root=self.root, font=font_spec)
        return self._font_cache[font_spec].measure(text)

    def rounded(self, x1, y1, x2, y2, radius, **options):
        radius = max(2, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
        points = [
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        ]
        return self.canvas.create_polygon(points, smooth=True, splinesteps=16, **options)

    def paper(self, x1, y1, x2, y2, radius=12, fill=None, shadow=6, **options):
        """A card with a soft drop shadow, like paper lying on the desk."""
        if shadow:
            self.rounded(x1 + shadow, y1 + shadow, x2 + shadow, y2 + shadow, radius,
                         fill=SHADOW, outline="")
        return self.rounded(x1, y1, x2, y2, radius, fill=fill or self.theme["paper"],
                            outline="", **options)

    def pin(self, x, y, colour=None):
        colour = colour or self.theme["accent"]
        self.canvas.create_oval(x - 8, y - 6, x + 10, y + 12, fill=SHADOW, outline="")
        self.canvas.create_oval(x - 9, y - 9, x + 9, y + 9, fill=colour, outline="")
        self.canvas.create_oval(x - 5, y - 6, x - 1, y - 2, fill="#FFFFFF", outline="")

    def rotated_box(self, cx, cy, width, height, angle):
        """Corner points of a box rotated anticlockwise by angle degrees."""
        radians = math.radians(angle)
        points = []
        for dx, dy in [(-width / 2, -height / 2), (width / 2, -height / 2),
                       (width / 2, height / 2), (-width / 2, height / 2)]:
            points += [cx + dx * math.cos(radians) + dy * math.sin(radians),
                       cy - dx * math.sin(radians) + dy * math.cos(radians)]
        return points

    def stamp(self, cx, cy, text, colour, angle=8, size=20, fill=""):
        """A rubber-stamp label: double border and rotated capital letters."""
        font_spec = self.font("mono", size, "bold")
        width = self.text_width(font_spec, text) + size * 1.6
        height = size * 2.4
        self.canvas.create_polygon(self.rotated_box(cx, cy, width, height, angle),
                                   fill=fill, outline=colour, width=3)
        self.canvas.create_polygon(self.rotated_box(cx, cy, width - 10, height - 10, angle),
                                   fill="", outline=colour, width=1)
        self.canvas.create_text(cx, cy, text=text, angle=angle, fill=colour, font=font_spec)

    def button(self, x1, y1, x2, y2, text, command, tag, size=13):
        self.rounded(x1 + 3, y1 + 5, x2 + 3, y2 + 5, 12, fill=self.theme["accent_dark"],
                     outline="", tags=tag)
        self.rounded(x1, y1, x2, y2, 12, fill=self.theme["accent"], outline="", tags=tag)
        self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=text, fill="#FFFFFF",
                                font=self.font("sans", size, "bold"), tags=tag)
        self.canvas.tag_bind(tag, "<Button-1>", lambda _event: command())
        self.canvas.tag_bind(tag, "<Enter>", lambda _event: self.canvas.config(cursor="hand2"))
        self.canvas.tag_bind(tag, "<Leave>", lambda _event: self.canvas.config(cursor=""))

    def key_cap(self, x, y, label, colour=None, anchor="w"):
        """A small keyboard-key label such as [ENTER] or [1]; returns its width."""
        colour = colour or self.theme["ink_soft"]
        font_spec = self.font("mono", 9, "bold")
        width = self.text_width(font_spec, label) + 14
        x1 = x if anchor == "w" else x - width
        self.rounded(x1, y - 11, x1 + width, y + 11, 5, fill="", outline=colour, width=1)
        self.canvas.create_text(x1 + width / 2, y, text=label, fill=colour, font=font_spec)
        return width

    def photo(self, path, box, cover=False):
        """Draw a picture centred inside box and return the canvas item id."""
        x1, y1, x2, y2 = box
        image = self.images.fitted(path, x2 - x1, y2 - y1, cover=cover)
        return self.canvas.create_image((x1 + x2) / 2, (y1 + y2) / 2, image=image)

    def difficulty_chip(self, x, y, level):
        label = DIFFICULTY_LABELS[level].upper()
        font_spec = self.font("mono", 9, "bold")
        width = self.text_width(font_spec, label) + 20
        self.rounded(x, y - 11, x + width, y + 11, 11, fill=DIFFICULTY_COLOURS[level], outline="")
        self.canvas.create_text(x + width / 2, y, text=label, fill="#FFFFFF", font=font_spec)
        return width

    def tick_or_cross(self, x, y, correct, radius=10):
        colour = self.theme["success"] if correct else self.theme["danger"]
        self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius,
                                fill=colour, outline="")
        r = radius * 0.45
        if correct:
            self.canvas.create_line(x - r, y, x - r * 0.2, y + r * 0.8, x + r * 1.1, y - r * 0.8,
                                    fill="#FFFFFF", width=2.5)
        else:
            self.canvas.create_line(x - r, y - r, x + r, y + r, fill="#FFFFFF", width=2.5)
            self.canvas.create_line(x - r, y + r, x + r, y - r, fill="#FFFFFF", width=2.5)

    # ------------------------------------------------------------ drawing

    def _schedule_redraw(self, _event=None):
        if self.redraw_job is not None:
            self.root.after_cancel(self.redraw_job)
        self.redraw_job = self.root.after(40, self.draw)

    def draw(self):
        self.redraw_job = None
        self._stop_flicker()
        self.hover_index = None
        self.card_boxes = []
        self.canvas.delete("all")
        width = max(self.canvas.winfo_width(), 1040)
        height = max(self.canvas.winfo_height(), 700)
        self.draw_desk(width, height)
        self.draw_header(width)
        if self.screen == "start":
            self.draw_start(width, height)
        elif self.screen == "game":
            self.draw_game(width, height)
            self._hover_from_pointer()
        else:
            self.draw_result(width, height)

    def draw_desk(self, width, height):
        for x in range(0, width, 44):
            self.canvas.create_line(x, 0, x, height, fill=self.theme["desk_light"])
        for y in range(0, height, 44):
            self.canvas.create_line(0, y, width, y, fill=self.theme["desk_light"])

    def draw_header(self, width):
        theme = self.theme
        self.canvas.create_rectangle(0, 0, width, 70, fill=theme["desk"], outline="")
        self.canvas.create_oval(36, 17, 72, 53, fill=theme["accent"], outline="")
        self.canvas.create_oval(45, 25, 60, 40, outline="#FFFFFF", width=3)
        self.canvas.create_line(58, 38, 65, 46, fill="#FFFFFF", width=3)
        self.canvas.create_text(86, 28, text="PHOTO DETECTIVE", anchor="w",
                                fill=theme["on_desk"], font=self.font("mono", 16, "bold"))
        self.canvas.create_text(86, 48, text="VISUAL FORENSICS UNIT", anchor="w",
                                fill=theme["on_desk_soft"], font=self.font("mono", 9, "bold"))

        # A luggage-tag shaped badge showing the best score from scores.txt.
        best_text = f"BEST  {load_high_score()}"
        tag_font = self.font("mono", 11, "bold")
        tag_width = self.text_width(tag_font, best_text) + 46
        x2 = width - 40
        self.rounded(x2 - tag_width, 20, x2, 50, 6, fill=theme["folder"], outline="")
        self.canvas.create_oval(x2 - tag_width + 9, 31, x2 - tag_width + 17, 39,
                                fill=theme["desk"], outline="")
        self.canvas.create_text(x2 - 12, 35, text=best_text, anchor="e",
                                fill=theme["ink"], font=tag_font)
        games = len(load_scores())
        self.canvas.create_text(x2 - tag_width - 16, 35, text=f"GAMES PLAYED  {games}",
                                anchor="e", fill=theme["on_desk_soft"],
                                font=self.font("mono", 9, "bold"))

    # ---- start screen

    def draw_start(self, width, height):
        theme = self.theme
        pad, top, bottom = 40, 96, height - 36
        folder_x1 = pad
        folder_x2 = pad + (width - pad * 2) * 0.5
        body_top = top + 30
        body_height = bottom - body_top

        # Manila folder with a tab.
        self.rounded(folder_x1 + 6, top + 6, folder_x1 + 246, top + 50, 10, fill=SHADOW, outline="")
        self.rounded(folder_x1, top, folder_x1 + 240, top + 44, 10, fill=theme["folder_dark"], outline="")
        self.canvas.create_text(folder_x1 + 20, top + 16, text="CASE FILE  No. 0427", anchor="w",
                                fill=theme["ink"], font=self.font("mono", 10, "bold"))
        self.paper(folder_x1, body_top, folder_x2, bottom, radius=14, fill=theme["folder"])
        self.stamp(folder_x2 - 112, body_top + 52, "CONFIDENTIAL", theme["accent"], angle=9, size=12)

        left = folder_x1 + 40
        inner_width = folder_x2 - left - 40

        def at(fraction):
            return body_top + body_height * fraction

        title_size = 38 if height >= 790 else 32
        self.canvas.create_text(left, at(0.08), text="SPOT THE\nCLOSEST MATCH", anchor="nw",
                                fill=theme["ink"], font=self.font("serif", title_size, "bold"))
        subtitle = self.canvas.create_text(
            left, at(0.30), anchor="nw", width=inner_width, fill=theme["ink_soft"],
            font=self.font("sans", 13 if height >= 790 else 12),
            text="Study the evidence photo, question four suspects and accuse the "
                 "one that really matches. Then read the forensic report to see why.",
        )
        # Lay the next block out below wherever the subtitle actually ended.
        ladder_y = max(at(0.44), self.canvas.bbox(subtitle)[3] + 22)

        # Difficulty ladder: five bars that grow taller, one per case.
        self.canvas.create_text(left, ladder_y, anchor="w", fill=theme["ink"],
                                text="FIVE CASES  ·  EACH ONE HARDER",
                                font=self.font("mono", 10, "bold"))
        gap = 8
        bar_width = (inner_width - gap * 4) / 5
        base = ladder_y + 70
        for level in range(1, 6):
            x1 = left + (level - 1) * (bar_width + gap)
            bar_height = 10 + level * 9
            self.rounded(x1, base - bar_height, x1 + bar_width, base, 5,
                         fill=DIFFICULTY_COLOURS[level], outline="")
            self.canvas.create_text(x1 + bar_width / 2, base + 13,
                                    text=DIFFICULTY_LABELS[level].upper(), fill=theme["ink"],
                                    font=self.font("mono", 8, "bold"))

        button_top = max(at(0.67), base + 38)
        button_width = min(310, inner_width)
        self.button(left, button_top, left + button_width, button_top + 58,
                    "START INVESTIGATION  →", self.start_game, tag="start", size=14)
        hint_y = button_top + 29
        if inner_width - button_width > 150:
            key_width = self.key_cap(left + button_width + 24, hint_y, "ENTER")
            self.canvas.create_text(left + button_width + 32 + key_width, hint_y, anchor="w",
                                    text="also works", fill=theme["ink_soft"],
                                    font=self.font("sans", 11))

        # Three-step how-to strip along the bottom of the folder.
        self.canvas.create_line(left, at(0.84), folder_x2 - 40, at(0.84),
                                fill=theme["folder_dark"], width=2)
        steps = ["Study the evidence", "Hover to flicker-test", "Press 1-4 to accuse"]
        step_width = inner_width / 3
        for number, step in enumerate(steps, start=1):
            x = left + (number - 1) * step_width
            y = at(0.92)
            self.canvas.create_oval(x, y - 12, x + 24, y + 12, fill=theme["ink"], outline="")
            self.canvas.create_text(x + 12, y, text=str(number), fill=theme["folder"],
                                    font=self.font("mono", 10, "bold"))
            self.canvas.create_text(x + 32, y, text=step, anchor="w", fill=theme["ink"],
                                    width=step_width - 38, font=self.font("sans", 10, "bold"))

        self.draw_corkboard(folder_x2 + 28, top, width - pad, bottom)

    def draw_corkboard(self, x1, y1, x2, y2):
        theme = self.theme
        self.paper(x1, y1, x2, y2, radius=14, fill="#5A3E26")
        self.canvas.create_rectangle(x1 + 14, y1 + 14, x2 - 14, y2 - 14,
                                     fill=theme["cork"], outline="")
        speckles = random.Random(7)  # fixed seed so the texture never jumps
        for _ in range(int((x2 - x1) * (y2 - y1) / 520)):
            x = speckles.uniform(x1 + 16, x2 - 18)
            y = speckles.uniform(y1 + 16, y2 - 18)
            size = speckles.choice([1.5, 2, 2.5])
            colour = speckles.choice([theme["cork_dark"], "#C99A63", "#A47444"])
            self.canvas.create_oval(x, y, x + size, y + size, fill=colour, outline="")

        board_width, board_height = x2 - x1, y2 - y1
        layout = [(0.07, 0.07, 0.48), (0.47, 0.29, 0.44), (0.10, 0.58, 0.38)]
        pins = []
        for (path, caption), (fx, fy, fw) in zip(BOARD_PHOTOS, layout):
            px1 = x1 + board_width * fx
            py1 = y1 + board_height * fy
            photo_width = board_width * fw
            image_height = photo_width * 0.62
            px2, py2 = px1 + photo_width, py1 + image_height + 46
            self.paper(px1, py1, px2, py2, radius=3, shadow=5)
            self.photo(PROJECT_DIR / path, (px1 + 10, py1 + 10, px2 - 10, py1 + 10 + image_height),
                       cover=True)
            colour = theme["accent"] if caption == "EVIDENCE" else theme["ink"]
            self.canvas.create_text(px1 + 12, py2 - 18, text=caption, anchor="w", fill=colour,
                                    font=self.font("mono", 10, "bold"))
            pins.append(((px1 + px2) / 2, py1 + 4))

        evidence_pin = pins[0]
        for other in pins[1:]:
            self.canvas.create_line(*evidence_pin, *other, fill=theme["accent"], width=2)
        for x, y in pins:
            self.pin(x, y)

        # Sticky note with the question.
        note_x, note_y = x1 + board_width * 0.74, y1 + board_height * 0.80
        note_w, note_h = board_width * 0.34, board_height * 0.24
        self.canvas.create_polygon(self.rotated_box(note_x + 5, note_y + 6, note_w, note_h, -4),
                                   fill=SHADOW, outline="")
        self.canvas.create_polygon(self.rotated_box(note_x, note_y, note_w, note_h, -4),
                                   fill="#F6D867", outline="")
        self.canvas.create_text(note_x, note_y, angle=-4, justify="center", fill=theme["ink"],
                                text="WHICH SUSPECT\nIS THE REAL\nMATCH?",
                                font=self.font("mono", 12, "bold"))
        self.pin(note_x, note_y - note_h / 2 + 10, colour=theme["ink"])

    # ---- game screen

    def draw_game(self, width, height):
        theme, case = self.theme, self.current_case
        pad = 40

        # Case heading.
        self.canvas.create_text(pad, 96, anchor="w", fill=theme["accent"],
                                text=f"CASE {self.round_index + 1} OF {CASES_PER_GAME}",
                                font=self.font("mono", 11, "bold"))
        self.difficulty_chip(pad + 112, 96, case["difficulty"])
        self.canvas.create_text(pad, 126, anchor="w", fill=theme["on_desk"], text=case["title"],
                                font=self.font("serif", 22, "bold"))

        # Progress pips, one per case: green tick, red cross, amber = now.
        for index in range(CASES_PER_GAME):
            x = width - pad - 10 - (CASES_PER_GAME - 1 - index) * 30
            if index < len(self.history):
                self.tick_or_cross(x, 98, self.history[index]["correct"], radius=10)
            elif index == self.round_index:
                self.canvas.create_oval(x - 10, 88, x + 10, 108, outline=theme["amber"], width=3)
            else:
                self.canvas.create_oval(x - 9, 89, x + 9, 107, fill=theme["desk_light"], outline="")
        self.canvas.create_text(width - pad, 128, anchor="e", fill=theme["on_desk_soft"],
                                text=f"SCORE  {self.score}", font=self.font("mono", 11, "bold"))

        footer_height = 100
        body_top, body_bottom = 156, height - footer_height - 34
        evidence_x2 = pad + (width - pad * 2) * 0.40
        self.draw_evidence(pad, body_top, evidence_x2, body_bottom)

        gap = 18
        cards_x1 = evidence_x2 + 26
        card_width = (width - pad - cards_x1 - gap) / 2
        card_height = (body_bottom - body_top - gap) / 2
        for index, suspect in enumerate(case["candidates"]):
            row, column = divmod(index, 2)
            x1 = cards_x1 + column * (card_width + gap)
            y1 = body_top + row * (card_height + gap)
            box = (x1, y1, x1 + card_width, y1 + card_height)
            self.card_boxes.append(box)
            self.draw_suspect(index, suspect, box)

        footer = (pad, height - footer_height - 14, width - pad, height - 14)
        if self.answered:
            self.draw_report(*footer)
        else:
            self.draw_instructions(*footer)

    def draw_evidence(self, x1, y1, x2, bottom):
        """Evidence polaroid sized to the photo, with case notes underneath."""
        theme = self.theme
        source_width, source_height = self.images.size(self.current_case["reference"])
        image_width = x2 - x1 - 32
        image_height = min(image_width * source_height / source_width, bottom - y1 - 200)
        y2 = y1 + 22 + image_height + 56
        if bottom - y2 < 110:            # small window: no room for notes
            y2 = bottom
        self.evidence_frame = self.paper(x1, y1, x2, y2, radius=6, width=4)
        self.canvas.itemconfigure(self.evidence_frame, outline=theme["paper"])
        self.evidence_box = (x1 + 16, y1 + 22, x2 - 16, y2 - 56)
        self.evidence_item = self.photo(self.current_case["reference"], self.evidence_box)
        self.evidence_label = self.canvas.create_text(
            x1 + 18, y2 - 28, anchor="w", text="EVIDENCE", fill=theme["accent"],
            font=self.font("mono", 12, "bold"))
        self.evidence_note = self.canvas.create_text(
            x2 - 18, y2 - 28, anchor="e", text="reference photo", fill=theme["ink_soft"],
            font=self.font("mono", 10))
        self.pin((x1 + x2) / 2, y1 + 4)

        if y2 == bottom:
            return
        level = self.current_case["difficulty"]
        notes_top = y2 + 18
        self.paper(x1, notes_top, x2, bottom, radius=8, fill=theme["desk_light"], shadow=0)
        self.canvas.create_text(x1 + 18, notes_top + 22, anchor="w", text="CASE NOTES",
                                fill=theme["on_desk_soft"], font=self.font("mono", 10, "bold"))
        self.canvas.create_text(x2 - 18, notes_top + 22, anchor="e",
                                text=f"LEVEL {level} OF 5", fill=DIFFICULTY_COLOURS[level],
                                font=self.font("mono", 10, "bold"))
        self.canvas.create_text(x1 + 18, notes_top + 42, anchor="nw", width=x2 - x1 - 36,
                                text=DIFFICULTY_NOTES[level], fill=theme["on_desk"],
                                font=self.font("sans", 11))

    def draw_suspect(self, index, suspect, box):
        theme, case = self.theme, self.current_case
        x1, y1, x2, y2 = box
        is_best = index == case["best_index"]
        is_selected = index == self.selected

        outline, outline_width = "", 0
        if self.answered and is_best:
            outline, outline_width = theme["success"], 4
        elif self.answered and is_selected:
            outline, outline_width = theme["danger"], 4
        card = self.paper(x1, y1, x2, y2, radius=6, shadow=5)
        if outline:
            self.canvas.itemconfigure(card, outline=outline, width=outline_width)
        # Invisible-until-hover outline used by the flicker test.
        self.canvas.create_rectangle(x1 - 5, y1 - 5, x2 + 5, y2 + 5, outline="", width=3,
                                     tags=("hover", f"hover_{index}"))

        image_box = (x1 + 10, y1 + 10, x2 - 10, y2 - 52)
        self.photo(suspect["path"], image_box)

        self.canvas.create_text(x1 + 14, y2 - 34, anchor="w", text=f"SUSPECT {index + 1}",
                                fill=theme["ink"], font=self.font("mono", 11, "bold"))
        if not self.answered:
            self.key_cap(x2 - 12, y2 - 34, str(index + 1), anchor="e")
            self.canvas.create_text(x1 + 14, y2 - 14, anchor="w", fill=theme["ink_soft"],
                                    text="hover to flicker-test", font=self.font("mono", 8))
            return

        scores = suspect["scores"]
        colour = theme["success"] if is_best else theme["ink"]
        self.canvas.create_text(x2 - 12, y2 - 34, anchor="e", fill=colour,
                                text=f"{scores['overall']:.1f}%",
                                font=self.font("mono", 12, "bold"))
        # Four mini bars. Each clue is scaled within this case (weakest suspect
        # gets a short bar) so even Expert-level differences are visible.
        segment = (x2 - x1 - 28) / 4
        for number, (key, short_name) in enumerate(CLUES):
            sx = x1 + 14 + number * segment
            self.canvas.create_text(sx, y2 - 13, anchor="w", text=short_name,
                                    fill=theme["ink_soft"], font=self.font("mono", 8, "bold"))
            bar_x1, bar_x2 = sx + 28, sx + segment - 8
            values = [other["scores"][key] for other in case["candidates"]]
            low, high = min(values), max(values)
            fill = 1.0 if high - low < 0.05 else 0.15 + 0.85 * (scores[key] - low) / (high - low)
            self.canvas.create_rectangle(bar_x1, y2 - 16, bar_x2, y2 - 10,
                                         fill="#E4DCCB", outline="")
            self.canvas.create_rectangle(bar_x1, y2 - 16, bar_x1 + (bar_x2 - bar_x1) * fill,
                                         y2 - 10, fill=colour, outline="")

        centre_x, centre_y = (x1 + x2) / 2, (y1 + y2 - 42) / 2
        if is_best:
            self.stamp(centre_x, centre_y, "MATCH", theme["success"], angle=10, size=20,
                       fill=theme["paper"])
        elif is_selected:
            self.stamp(centre_x, centre_y, "WRONG", theme["danger"], angle=-9, size=20,
                       fill=theme["paper"])

    def draw_instructions(self, x1, y1, x2, y2):
        theme = self.theme
        self.paper(x1, y1, x2, y2, radius=10, fill=theme["folder"], shadow=5)
        self.canvas.create_text(x1 + 24, y1 + 26, anchor="w", text="HOW TO SOLVE",
                                fill=theme["accent"], font=self.font("mono", 11, "bold"))
        self.canvas.create_text(
            x1 + 24, y1 + 44, anchor="nw", width=(x2 - x1) * 0.66, fill=theme["ink"],
            font=self.font("sans", 11),
            text="Hover over a suspect: it flickers in place of the evidence, so any "
                 "change in brightness, colour or framing jumps out. Click the suspect "
                 "you think matches best, or press its number key.",
        )
        x = x2 - 24
        for label in ["4", "3", "2", "1"]:
            x -= self.key_cap(x, (y1 + y2) / 2, label, colour=theme["ink"], anchor="e") + 8
        self.canvas.create_text(x - 8, (y1 + y2) / 2, anchor="e", text="ACCUSE", fill=theme["ink"],
                                font=self.font("mono", 10, "bold"))

    def draw_report(self, x1, y1, x2, y2):
        theme, case = self.theme, self.current_case
        best_number = case["best_index"] + 1
        best = case["candidates"][case["best_index"]]
        correct = self.selected == case["best_index"]
        self.paper(x1, y1, x2, y2, radius=10, fill=theme["folder"], shadow=5)

        self.canvas.create_text(x1 + 24, y1 + 24, anchor="w", text="FORENSIC REPORT",
                                fill=theme["ink_soft"], font=self.font("mono", 10, "bold"))
        if correct:
            verdict = "MATCH CONFIRMED  +100"
        else:
            chosen = case["candidates"][self.selected]
            verdict = f"WRONG SUSPECT  +0   (#{self.selected + 1}: {chosen.get('change', 'edited')})"
        self.canvas.create_text(x1 + 190, y1 + 24, anchor="w", text=verdict,
                                fill=theme["success"] if correct else theme["danger"],
                                font=self.font("mono", 13, "bold"))

        if case["margin"] < 1:
            gap_text = f"by a razor-thin {case['margin']:.2f} points"
        else:
            gap_text = f"{case['margin']:.1f} points ahead of the next suspect"
        detail = (f"Suspect {best_number} is the closest match at "
                  f"{best['scores']['overall']:.1f}%, {gap_text}.")
        self.canvas.create_text(x1 + 24, y1 + 44, anchor="nw", width=(x2 - x1) - 290,
                                fill=theme["ink"], font=self.font("sans", 11), text=detail)
        self.canvas.create_text(
            x1 + 24, y2 - 16, anchor="w", fill=theme["ink_soft"], font=self.font("mono", 9),
            text="40% PIX(els) + 25% COL(our) + 20% LUM(inance) + 15% RAT(io)"
                 "  ·  bars compare suspects")

        last_case = self.round_index == CASES_PER_GAME - 1
        label = "FINAL VERDICT  →" if last_case else "NEXT CASE  →"
        self.button(x2 - 230, y1 + 22, x2 - 24, y2 - 22, label, self.next_round, tag="next")

    # ---- result screen

    def draw_result(self, width, height):
        theme = self.theme
        correct = sum(1 for entry in self.history if entry["correct"])
        games = load_scores()
        panel_width = min(980, width - 80)
        x1 = (width - panel_width) / 2
        x2 = x1 + panel_width
        top, bottom = 96, height - 36
        compact = height < 790

        self.rounded(x1 + 6, top + 6, x1 + 266, top + 50, 10, fill=SHADOW, outline="")
        self.rounded(x1, top, x1 + 260, top + 44, 10, fill=theme["folder_dark"], outline="")
        self.canvas.create_text(x1 + 20, top + 16, anchor="w", text="CASE FILE  ·  CLOSED",
                                fill=theme["ink"], font=self.font("mono", 10, "bold"))
        body_top = top + 30
        self.paper(x1, body_top, x2, bottom, radius=14, fill=theme["folder"])
        left, right = x1 + 44, x2 - 44

        # Score, rank and the CASE CLOSED stamp.
        score_font = self.font("serif", 46 if compact else 56, "bold")
        score_y = body_top + (20 if compact else 30)
        self.canvas.create_text(left, score_y, anchor="nw", text=str(self.score),
                                fill=theme["ink"], font=score_font)
        line_height = tkfont.Font(root=self.root, font=score_font).metrics("linespace")
        score_width = self.text_width(score_font, str(self.score))
        self.canvas.create_text(left + score_width + 12, score_y + line_height * 0.78, anchor="sw",
                                text=f"/ {CASES_PER_GAME * POINTS_PER_CASE} POINTS",
                                fill=theme["ink_soft"], font=self.font("mono", 12, "bold"))
        rank_y = score_y + line_height + 18
        rank_font = self.font("mono", 11, "bold")
        badge_x = left
        badges = [(rank_for(correct).upper(), theme["ink"], theme["amber"])]
        if self.score > self.best_before_game:
            badges.append(("NEW PERSONAL BEST", theme["amber"], theme["ink"]))
        for label, background, text_colour in badges:
            badge_width = self.text_width(rank_font, label) + 28
            self.rounded(badge_x, rank_y - 15, badge_x + badge_width, rank_y + 15, 15,
                         fill=background, outline="")
            self.canvas.create_text(badge_x + badge_width / 2, rank_y, text=label,
                                    fill=text_colour, font=rank_font)
            badge_x += badge_width + 10
        self.stamp(right - 140, score_y + line_height * 0.6, "CASE CLOSED", theme["accent"],
                   angle=-8, size=20 if compact else 24)

        # Case review: one mini polaroid per case.
        review_top = rank_y + (34 if compact else 44)
        self.canvas.create_text(left, review_top, anchor="w", text="CASE REVIEW",
                                fill=theme["ink"], font=self.font("mono", 10, "bold"))
        gap = 16
        card_width = (right - left - gap * (CASES_PER_GAME - 1)) / CASES_PER_GAME
        image_height = card_width * (0.42 if compact else 0.5)
        card_top = review_top + 16
        card_bottom = card_top + image_height + 54
        for index, entry in enumerate(self.history):
            cx1 = left + index * (card_width + gap)
            cx2 = cx1 + card_width
            self.paper(cx1, card_top, cx2, card_bottom, radius=4, shadow=4)
            self.photo(entry["reference"], (cx1 + 8, card_top + 8, cx2 - 8,
                                            card_top + 8 + image_height), cover=True)
            self.tick_or_cross(cx2 - 14, card_top + 14, entry["correct"], radius=11)
            level = entry["difficulty"]
            self.canvas.create_text(cx1 + 10, card_bottom - 30, anchor="w",
                                    text=DIFFICULTY_LABELS[level].upper(),
                                    fill=DIFFICULTY_COLOURS[level], font=self.font("mono", 9, "bold"))
            self.canvas.create_text(cx2 - 10, card_bottom - 30, anchor="e",
                                    text="+100" if entry["correct"] else "+0",
                                    fill=theme["ink"], font=self.font("mono", 10, "bold"))
            if entry["correct"]:
                note = f"found #{entry['best'] + 1}"
            else:
                note = f"chose #{entry['chosen'] + 1}, was #{entry['best'] + 1}"
            self.canvas.create_text(cx1 + 10, card_bottom - 12, anchor="w", text=note,
                                    fill=theme["ink_soft"], font=self.font("mono", 8))

        # Bottom bar: message and play-again button.
        button_y = bottom - 80
        messages = {
            5: "Flawless. Not a single suspect fooled you.",
            4: "Sharp eyes - only one suspect slipped past you.",
            3: "Solid work. Try the flicker test on the hardest cases.",
            2: "Getting there. Hover over suspects to flicker-test them.",
        }
        self.canvas.create_text(left, button_y + 29, anchor="w", width=right - left - 300,
                                text=messages.get(correct, "Every detective starts somewhere. Reopen the file!"),
                                fill=theme["ink"], font=self.font("sans", 13, "bold"))
        self.button(right - 256, button_y, right, button_y + 58, "PLAY AGAIN  ↻",
                    self.start_game, tag="again", size=14)
        self.canvas.create_text(right - 128, bottom - 10, text="or press ENTER",
                                fill=theme["ink_soft"], font=self.font("mono", 9))

        # Middle band: stats on the left, recent games chart on the right.
        band_top, band_bottom = card_bottom + 26, button_y - 22
        if band_bottom - band_top < 70:
            return
        self.canvas.create_line(left, band_top - 10, right, band_top - 10,
                                fill=theme["folder_dark"], width=2)
        stats = [
            (f"{correct}/{CASES_PER_GAME}", "CORRECT"),
            (f"{round(correct / CASES_PER_GAME * 100)}%", "ACCURACY"),
            (str(load_high_score()), "BEST EVER"),
            (str(len(games)), "GAMES PLAYED"),
        ]
        stats_right = left + (right - left) * 0.48
        chip_width = (stats_right - left - 12) / 2
        chip_height = min(62, (band_bottom - band_top - 10) / 2)
        for index, (value, label) in enumerate(stats):
            row, column = divmod(index, 2)
            sx1 = left + column * (chip_width + 12)
            sy1 = band_top + row * (chip_height + 10)
            self.rounded(sx1, sy1, sx1 + chip_width, sy1 + chip_height, 8,
                         fill=theme["paper"], outline="")
            self.canvas.create_text(sx1 + 16, sy1 + chip_height / 2, anchor="w", text=value,
                                    fill=theme["ink"], font=self.font("serif", 18, "bold"))
            self.canvas.create_text(sx1 + chip_width - 14, sy1 + chip_height / 2, anchor="e",
                                    text=label, fill=theme["ink_soft"],
                                    font=self.font("mono", 9, "bold"))
        self.draw_history_chart(stats_right + 36, band_top, right, band_top + chip_height * 2 + 10,
                                games)

    def draw_history_chart(self, x1, y1, x2, y2, games):
        """Bar chart of the last ten scores read back from scores.txt."""
        theme = self.theme
        recent = games[-10:]
        self.canvas.create_text(x1, y1 + 6, anchor="w", text="YOUR LAST GAMES",
                                fill=theme["ink"], font=self.font("mono", 10, "bold"))
        self.canvas.create_text(x2, y1 + 6, anchor="e", text="from data/scores.txt",
                                fill=theme["ink_soft"], font=self.font("mono", 8))
        if not recent:
            return
        maximum = CASES_PER_GAME * POINTS_PER_CASE
        base, plot_top = y2 - 14, y1 + 34
        slot = (x2 - x1) / 10
        bar_width = min(26, slot - 6)
        best = max(recent)
        self.canvas.create_line(x1, base, x2, base, fill=theme["folder_dark"], width=1)
        for index, game in enumerate(recent):
            bx = x1 + index * slot + (slot - bar_width) / 2
            bar_height = max(3, (base - plot_top) * game / maximum)
            is_latest = index == len(recent) - 1
            colour = theme["accent"] if is_latest else theme["ink_soft"]
            self.rounded(bx, base - bar_height, bx + bar_width, base, 4, fill=colour, outline="")
            if is_latest or (game == best and best > 0):
                self.canvas.create_text(bx + bar_width / 2, base - bar_height - 9,
                                        text=str(game), fill=theme["ink"],
                                        font=self.font("mono", 8, "bold"))
            if is_latest:
                self.canvas.create_text(bx + bar_width / 2, base + 10, text="now",
                                        fill=theme["accent"], font=self.font("mono", 8, "bold"))

    # ------------------------------------------------------- flicker test

    def _card_at(self, x, y):
        for index, (x1, y1, x2, y2) in enumerate(self.card_boxes):
            if x1 <= x <= x2 and y1 <= y <= y2:
                return index
        return None

    def _hover_from_pointer(self):
        x = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx()
        y = self.canvas.winfo_pointery() - self.canvas.winfo_rooty()
        self._set_hover(self._card_at(x, y))

    def _on_motion(self, event):
        if self.screen == "game":
            self._set_hover(self._card_at(event.x, event.y))

    def _set_hover(self, index):
        if index == self.hover_index:
            return
        self._stop_flicker()
        self.canvas.itemconfigure("hover", outline="")
        self.hover_index = index
        if index is None:
            self.canvas.config(cursor="")
            return
        self.canvas.itemconfigure(f"hover_{index}", outline=self.theme["amber"])
        self.canvas.config(cursor="" if self.answered else "hand2")
        self.flicker_showing_suspect = False
        self._flicker_step()

    def _flicker_step(self):
        """Swap the evidence photo with the hovered suspect, again and again."""
        if self.hover_index is None or self.screen != "game":
            return
        self.flicker_showing_suspect = not self.flicker_showing_suspect
        x1, y1, x2, y2 = self.evidence_box
        if self.flicker_showing_suspect:
            path = self.current_case["candidates"][self.hover_index]["path"]
            label, note, colour = f"SUSPECT {self.hover_index + 1}", "flicker test", self.theme["amber_ink"]
        else:
            path = self.current_case["reference"]
            label, note, colour = "EVIDENCE", "flicker test", self.theme["accent"]
        image = self.images.fitted(path, x2 - x1, y2 - y1)
        self.canvas.itemconfigure(self.evidence_item, image=image)
        self.canvas.itemconfigure(self.evidence_label, text=label, fill=colour)
        self.canvas.itemconfigure(self.evidence_note, text=note)
        self.canvas.itemconfigure(self.evidence_frame, outline=self.theme["amber"])
        self.flicker_job = self.root.after(FLICKER_MS, self._flicker_step)

    def _stop_flicker(self):
        if self.flicker_job is not None:
            self.root.after_cancel(self.flicker_job)
            self.flicker_job = None
        if self.screen == "game" and self.current_case and self.card_boxes:
            x1, y1, x2, y2 = self.evidence_box
            image = self.images.fitted(self.current_case["reference"], x2 - x1, y2 - y1)
            self.canvas.itemconfigure(self.evidence_item, image=image)
            self.canvas.itemconfigure(self.evidence_label, text="EVIDENCE", fill=self.theme["accent"])
            self.canvas.itemconfigure(self.evidence_note, text="reference photo")
            self.canvas.itemconfigure(self.evidence_frame, outline=self.theme["paper"])

    # ------------------------------------------------------- game flow

    def start_game(self):
        self.round_cases = choose_cases(self.cases, CASES_PER_GAME, self.rng)
        self.round_index = 0
        self.score = 0
        self.history = []
        self.best_before_game = load_high_score()
        self.screen = "game"
        self.load_round()

    def load_round(self):
        case = self.round_cases[self.round_index]
        self.current_case = prepare_round(case, self.images.grid, self.rng)
        self.answered = False
        self.selected = None
        self.draw()

    def select_candidate(self, index):
        if self.screen != "game" or self.answered or not 0 <= index < 4:
            return
        self.selected = index
        self.answered = True
        correct = index == self.current_case["best_index"]
        if correct:
            self.score += POINTS_PER_CASE
        self.history.append({
            "reference": self.current_case["reference"],
            "difficulty": self.current_case["difficulty"],
            "best": self.current_case["best_index"],
            "chosen": index,
            "correct": correct,
        })
        self.draw()

    def next_round(self):
        if not self.answered:
            return
        if self.round_index < CASES_PER_GAME - 1:
            self.round_index += 1
            self.load_round()
        else:
            correct = sum(1 for entry in self.history if entry["correct"])
            save_score(self.score, correct, CASES_PER_GAME)
            self.screen = "result"
            self.draw()

    def _on_click(self, event):
        if self.screen == "game" and not self.answered:
            index = self._card_at(event.x, event.y)
            if index is not None:
                self.select_candidate(index)

    def _on_key(self, event):
        if self.screen == "game" and not self.answered and event.char in ("1", "2", "3", "4"):
            self.select_candidate(int(event.char) - 1)
        elif event.keysym in ("Return", "KP_Enter", "space"):
            if self.screen in ("start", "result"):
                self.start_game()
            elif self.answered:
                self.next_round()


def main():
    root = tk.Tk()
    if tk.TkVersion < 8.6:
        root.withdraw()
        messagebox.showerror(
            "Photo Detective needs a newer Python",
            "This Python uses Tk %s, which cannot open PNG images.\n\n"
            "Please run the game with Python 3.8+ from python.org "
            "(or Anaconda), which includes Tk 8.6." % tk.TkVersion,
        )
        root.destroy()
        return
    try:
        PhotoDetectiveApp(root)
    except (FileNotFoundError, ValueError, KeyError, tk.TclError) as error:
        root.withdraw()
        messagebox.showerror(
            "Photo Detective could not start",
            f"{error}\n\nKeep main.py together with the data and assets folders.",
        )
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    main()
