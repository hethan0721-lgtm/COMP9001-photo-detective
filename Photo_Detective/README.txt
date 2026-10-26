Photo Detective
COMP9001 Final Project


HOW TO RUN
==========

Entry point: main.py

Keep the project folder intact. Open a terminal in the project root and run:

    macOS / Linux:  python3 main.py
    Windows:        python main.py

Windows users may also double-click start.bat.

The game requires Python 3.8 or later and Tkinter 8.6 or later.

Some older macOS system or Command Line Tools Python installations use
Tk 8.5, which is too old to display the PNG images. The game will show a
warning in this situation. Please use Python from python.org or Anaconda
instead.


NOTE FOR THE MARKER
===================

This is a Tkinter desktop GUI application. It must be run locally on a
computer rather than in the Ed code runner.

The playable game uses only Python's standard library. It requires no pip
packages, internet connection, account, audio, video, or other software.

tools/build_assets.py is an optional development tool used to prepare the
image assets. It uses Pillow, as well as pillow-heif when processing HEIC files.
All finished PNG assets are already included, so the marker does not need to
run this tool or install either package.


ABOUT THE PROJECT
=================

Photo Detective is a visual observation game set around Sydney.

The project contains twelve cases. Each game randomly selects one case from
each of five difficulty levels and presents them in order from Easy to Expert.

Every case shows one evidence photograph and four suspects. The player chooses
the suspect that is the closest match. The program then calculates its own
answer from the image data and displays a similarity score for every option.


HOW TO PLAY
===========

- Click START or press Return to begin.
- Hover over a suspect to use the Flicker Test. The suspect and evidence
  images alternate so that small changes are easier to notice.
- Click a suspect or press a number key from 1 to 4 to make an accusation.
- Each correct answer earns 100 points. The maximum score is 500.
- The final screen shows the score, detective rank, and recent game history.

Different levels use different types of distractors. Easy and Medium mainly
use other scenes. Hard uses images that are mirrored, black and white, or
cropped to a wider shape. Very Hard uses darker, less colourful, or slightly
zoomed images. Expert recolours one small object in each distractor.


SIMILARITY CALCULATION
======================

Each image is converted into a 64 x 64 grid of RGB values. The program then
combines four measures:

- Pixel similarity: 40%
- Average colour similarity: 25%
- Brightness similarity: 20%
- Aspect ratio similarity: 15%

The program uses the highest unrounded overall score to select its answer.
Rounded scores are used only for display.

All similarity calculations are implemented in game_engine.py with loops and
basic mathematics. The playable game does not use a machine-learning model,
network service, or third-party image-analysis library.


ADVANCED TOPICS USED
====================

1. Multi-dimensional Lists

   image_tools.py stores image data as a three-dimensional list in the form
   rows[row][column][channel]. game_engine.py uses nested loops to compare the
   images pixel by pixel and channel by channel.

2. File I/O

   The program reads case data from data/cases.json and interface settings
   from theme.json. It writes scores to data/scores.txt and reads them back for
   the recent-game history. Exceptions handle missing or damaged files.

3. Testing

   The tests folder contains automated tests for the similarity calculations,
   case data, file handling, image loading, and complete game flow.


RUNNING THE TESTS
=================

Run the following command from the project root:

    python3 -m unittest discover -s tests -v

test_logic.py does not open a window. test_gui.py requires a desktop display
and is skipped automatically when a window cannot be created.


MAIN FILES
==========

main.py
    Game entry point, window, interface drawing, and player controls.

game_engine.py
    Case selection, similarity calculations, scoring, and score history.

image_tools.py
    PNG loading, three-dimensional pixel grids, and image resizing.

theme_manager.py
    Loading and validation of the settings in theme.json.

data/cases.json
    Data for the twelve cases.

assets/
    Reference images, matching images, and edited difficulty variants.

tests/
    Automated logic and GUI tests.

start.bat
    Windows double-click launcher.

tools/build_assets.py
    Optional development tool that prepared the image assets.


AI USE ACKNOWLEDGEMENT
================================

The twelve reference images consist of six photographs taken by me and six
Sydney scenes created with an AI image generator. All matching images and
edited variants were prepared with tools/build_assets.py.

GPT was used during development to assist with debugging,
suggest improvements, and refine the project documentation. I evaluated,
adapted, and verified all suggestions against the needs of the project. The
final submission has been fully reviewed and confirmed by me.
