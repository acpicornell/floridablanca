"""Split a page image into halves (top/bottom or quarters) so the
Read tool's downsample budget is spent on a smaller portion of the
page and we get higher effective resolution per cell.

Usage:
    python scripts/split_page.py 25     # writes page-25-top.jpg and page-25-bot.jpg
"""
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "data" / "pages"
OUT   = ROOT / "data" / "pages" / "crops"


def main():
    OUT.mkdir(exist_ok=True)
    for arg in sys.argv[1:]:
        n = int(arg)
        src = PAGES / f"page-{n:02d}.jpg"
        img = Image.open(src)
        w, h = img.size
        top = img.crop((0, 0, w, h // 2 + 60))            # +60 px overlap
        bot = img.crop((0, h // 2 - 60, w, h))
        top.save(OUT / f"page-{n:02d}-top.jpg", quality=92)
        bot.save(OUT / f"page-{n:02d}-bot.jpg", quality=92)
        print(f"{src.name} -> top {top.size}, bot {bot.size}")


if __name__ == "__main__":
    main()
