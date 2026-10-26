# Photo Detective: Sydney Case Files

A visual observation game set around Sydney, built with Python and Tkinter.
Each case shows one evidence photo and four suspects. Find the closest match,
then see the program's own answer and the similarity score of every suspect.

## Requirements

- Python 3.8 or later
- Tkinter 8.6 or later

No pip packages or internet connection are needed.

## Setup

Install Python from [python.org](https://www.python.org/downloads/). It includes Tkinter 8.6.

To check your Tk version:

```bash
python3 -c "import tkinter; print(tkinter.TkVersion)"
```

If it prints `8.5`, the game cannot display PNG images.
This happens with some older macOS system Python installations.
Use Python from python.org or Anaconda instead.

## How to Run

```bash
git clone <this repository's URL>
cd <repository folder>
python3 main.py
```

On Windows, run `python main.py`, or double-click `start.bat`.

Keep the `assets` and `data` folders next to `main.py`.

## How to Play

| Action | Mouse | Keyboard |
|---|---|---|
| Start a game | Click **START INVESTIGATION** | `Enter` |
| Flicker Test | Hover over a suspect | |
| Accuse a suspect | Click the suspect | `1` – `4` |
| Next case | Click **NEXT CASE** | `Enter` |

- Each game has five cases, from Easy to Expert.
- The Flicker Test swaps the suspect with the evidence photo, so small changes stand out.
- Each correct answer earns 100 points. The maximum score is 500.
- Scores are saved to `data/scores.txt`. The final screen shows your recent games.

| Level | Distractors |
|---|---|
| Easy | Completely different scenes |
| Medium | A similar kind of scene |
| Hard | Mirrored, black and white, or cropped wider |
| Very Hard | Darker, less colourful, or slightly zoomed |
| Expert | One small object recoloured |

## How Similarity Is Calculated

Each image is reduced to a 64 × 64 grid of RGB values. The program combines four measures:

| Measure | Weight |
|---|---|
| Pixel similarity | 40% |
| Average colour similarity | 25% |
| Brightness similarity | 20% |
| Aspect ratio similarity | 15% |

The suspect with the highest overall score is the program's answer.
All calculations are written by hand in `game_engine.py`, with no image-analysis library.
