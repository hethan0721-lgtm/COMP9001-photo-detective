"""Image loading for Photo Detective using only Python's standard library.

Tkinter (built into Python) can decode PNG files. We ask Tk to hand the
decoded picture back as raw PPM bytes, then do everything else ourselves:

* PixelGrid turns those bytes into a 3-D list  grid[row][column] = [r, g, b]
  that game_engine.py uses for the similarity maths.
* ImageLibrary resizes pictures for the screen with nearest-neighbour
  sampling and caches the results so redrawing the window stays fast.

No Pillow or other third-party package is needed.
"""

import tkinter as tk
from pathlib import Path

GRID_SIZE = 64  # every picture is summarised as a 64 x 64 grid of colours


def read_ppm_bytes(photo):
    """Return (width, height, raw_rgb_bytes) for a loaded tk.PhotoImage."""
    data = photo.tk.call(str(photo), "data", "-format", "ppm")
    if isinstance(data, str):  # some older Tk builds return text, not bytes
        data = data.encode("latin-1")
    magic, size, maximum, pixels = data.split(b"\n", 3)
    if magic != b"P6" or maximum != b"255":
        raise ValueError("Tk returned an unexpected image format.")
    width, height = (int(value) for value in size.split())
    return width, height, pixels


class PixelGrid:
    """A picture summarised as rows of [red, green, blue] lists.

    The grid is a genuine multi-dimensional list:
        self.rows[row][column][channel]
    Each cell is the average of a 2 x 2 block of samples, which keeps fine
    textures from dominating the comparison.
    """

    def __init__(self, rows, width, height):
        self.rows = rows          # list of rows -> list of cells -> [r, g, b]
        self.width = width        # size of the ORIGINAL picture in pixels
        self.height = height

    @classmethod
    def from_ppm(cls, width, height, pixels, size=GRID_SIZE):
        stride = width * 3
        rows = []
        for row in range(size):
            cells = []
            for column in range(size):
                total = [0, 0, 0]
                for sub_y in (0.25, 0.75):
                    y = min(height - 1, int((row + sub_y) * height / size))
                    for sub_x in (0.25, 0.75):
                        x = min(width - 1, int((column + sub_x) * width / size))
                        start = y * stride + x * 3
                        for channel in range(3):
                            total[channel] += pixels[start + channel]
                cells.append([value / 4 for value in total])
            rows.append(cells)
        return cls(rows, width, height)

    @property
    def aspect_ratio(self):
        return self.width / self.height


class ImageLibrary:
    """Loads each PNG once and hands out grids and screen-sized copies."""

    def __init__(self, master):
        self.master = master
        self._sources = {}  # path -> (width, height, raw bytes)
        self._grids = {}    # path -> PixelGrid
        self._scaled = {}   # (path, width, height) -> tk.PhotoImage

    def _source(self, path):
        key = str(path)
        if key not in self._sources:
            if not Path(path).exists():
                raise FileNotFoundError(f"Missing picture: {path}")
            photo = tk.PhotoImage(master=self.master, file=key)
            self._sources[key] = read_ppm_bytes(photo)
        return self._sources[key]

    def size(self, path):
        width, height, _pixels = self._source(path)
        return width, height

    def grid(self, path):
        key = str(path)
        if key not in self._grids:
            self._grids[key] = PixelGrid.from_ppm(*self._source(path))
        return self._grids[key]

    def fitted(self, path, box_width, box_height, cover=False):
        """Return a PhotoImage scaled to fit (or, with cover=True, fill) a box."""
        source_width, source_height, pixels = self._source(path)
        if cover:
            scale = max(box_width / source_width, box_height / source_height)
            width, height = max(1, int(box_width)), max(1, int(box_height))
        else:
            scale = min(box_width / source_width, box_height / source_height)
            width = max(1, int(source_width * scale))
            height = max(1, int(source_height * scale))
        key = (str(path), width, height, cover)
        if key not in self._scaled:
            self._scaled[key] = self._resize(
                source_width, source_height, pixels, width, height, scale
            )
        return self._scaled[key]

    def _resize(self, source_width, source_height, pixels, width, height, scale):
        """Nearest-neighbour resize, centred, built row by row as PPM bytes."""
        left = (source_width - width / scale) / 2
        top = (source_height - height / scale) / 2
        columns = [
            min(source_width - 1, max(0, int(left + (x + 0.5) / scale))) * 3
            for x in range(width)
        ]
        stride = source_width * 3
        finished_rows = {}
        output = []
        for y in range(height):
            source_y = min(source_height - 1, max(0, int(top + (y + 0.5) / scale)))
            if source_y not in finished_rows:
                line = pixels[source_y * stride:(source_y + 1) * stride]
                finished_rows[source_y] = b"".join(line[x:x + 3] for x in columns)
            output.append(finished_rows[source_y])
        header = f"P6\n{width} {height}\n255\n".encode("ascii")
        return tk.PhotoImage(master=self.master, data=header + b"".join(output), format="ppm")