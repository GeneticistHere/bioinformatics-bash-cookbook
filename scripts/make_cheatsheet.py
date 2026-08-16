#!/usr/bin/env python3
"""Render the one-page trap cheat sheet to assets/cheatsheet.png.

Built from the HERO list in recipes.py, so the poster cannot drift from the
tested recipes. Writes an HTML page and screenshots it with headless Chrome.

    python3 scripts/make_cheatsheet.py

Chrome is only needed to rasterise. If it is missing, the HTML is still
written and can be printed to PNG from any browser at 1200px wide.
"""

import html
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from recipes import HERO, RECIPES, get   # noqa: E402

ASSETS = os.path.join(ROOT, "assets")
WIDTH, HEIGHT = 1200, 1100

REPO = "github.com/GeneticistHere/bioinformatics-bash-cookbook"

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
]

# Okabe-Ito on white, matching R/theme_case.R in the ggplot2 gallery.
CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
html { background: #ffffff; }
body {
  width: %(w)dpx; min-height: %(h)dpx;
  background: #ffffff;
  font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  padding: 50px 54px 0 54px;
  color: #000000;
}
h1 { font-size: 38px; font-weight: 700; letter-spacing: -0.4px; }
.sub {
  font-size: 18px; color: #3d3d3d; margin-top: 11px; line-height: 1.45;
}
.rows { margin-top: 30px; }
.row {
  display: grid; grid-template-columns: 40px 1fr;
  padding: 13px 0 14px 0;
  border-top: 1px solid #dcdcdc;
}
.row:last-child { border-bottom: 1px solid #dcdcdc; }
.num {
  font-size: 17px; color: #8a8a8a; font-weight: 700; padding-top: 4px;
  font-variant-numeric: tabular-nums;
}
.cmd {
  font-family: "SF Mono", Menlo, Consolas, monospace;
  font-size: 15px; line-height: 1.62; white-space: nowrap;
}
.bad  { color: #C0392B; }
.good { color: #007a59; }
.mark { display: inline-block; width: 20px; font-weight: 700; }
.why {
  font-size: 14px; color: #3d3d3d; margin-top: 6px; line-height: 1.4;
}
.id { color: #8a8a8a; }
footer {
  margin-top: 26px; display: flex; justify-content: space-between;
  align-items: baseline;
}
.repo {
  font-family: "SF Mono", Menlo, Consolas, monospace;
  font-size: 17px; color: #0072B2;
}
.stats { font-size: 15px; color: #8a8a8a; }
""" % {"w": WIDTH, "h": HEIGHT}


def row_html(n, rid, wrong, right, why):
    return """    <div class="row">
      <div class="num">%02d</div>
      <div>
        <div class="cmd bad"><span class="mark">&#10007;</span>%s</div>
        <div class="cmd good"><span class="mark">&#10003;</span>%s</div>
        <div class="why">%s <span class="id">(%s)</span></div>
      </div>
    </div>""" % (n, html.escape(wrong), html.escape(right),
                 html.escape(why), rid)


def build_html():
    rows = []
    for n, (rid, wrong, right) in enumerate(HERO, 1):
        why = get(rid)["trap"].split(". ")[0].rstrip(".")
        rows.append(row_html(n, rid, wrong, right, why))

    n_traps = sum(1 for r in RECIPES if r.get("trap"))
    return """<!doctype html>
<html><head><meta charset="utf-8"><style>%s</style></head>
<body>
  <h1>Ten bioinformatics one-liners that are quietly wrong</h1>
  <div class="sub">
    Each of these runs without an error and prints a plausible number.
    The number is not what you think it is.
  </div>
  <div class="rows">
%s
  </div>
  <footer>
    <div class="repo">%s</div>
    <div class="stats">%d recipes &middot; %d traps &middot;
      every command tested in CI</div>
  </footer>
  <script>
    // Publish the laid-out height so the renderer can size the canvas exactly
    // instead of guessing and clipping the last row.
    document.title = "H" + Math.ceil(
      document.body.getBoundingClientRect().height + 40);
  </script>
</body></html>
""" % (CSS, "\n".join(rows), REPO, len(RECIPES), n_traps)


def find_chrome():
    for path in CHROME_CANDIDATES:
        if path and os.path.exists(path):
            return path
    return None


def main():
    os.makedirs(ASSETS, exist_ok=True)
    page = os.path.join(ASSETS, "cheatsheet.html")
    png = os.path.join(ASSETS, "cheatsheet.png")

    with open(page, "w") as fh:
        fh.write(build_html())
    print("wrote", os.path.relpath(page, ROOT))

    chrome = find_chrome()
    if not chrome:
        print("Chrome not found - open the HTML and export it at "
              "%dpx wide" % WIDTH)
        return

    # Pass 1: let the browser lay the page out and report how tall it came out.
    probe = subprocess.run(
        [chrome, "--headless=new", "--disable-gpu", "--dump-dom",
         "--virtual-time-budget=3000",
         "--window-size=%d,%d" % (WIDTH, HEIGHT), "file://" + page],
        capture_output=True, text=True)
    found = re.search(r"<title>H(\d+)</title>", probe.stdout)
    height = int(found.group(1)) if found else HEIGHT
    print("measured content height: %dpx" % height)

    # Pass 2: 2x device scale so the PNG stays crisp when LinkedIn re-encodes it
    cmd = [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
           "--force-device-scale-factor=2",
           "--screenshot=" + png,
           "--window-size=%d,%d" % (WIDTH, height),
           "file://" + page]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if not os.path.exists(png):
        print("screenshot failed:\n" + proc.stderr[-800:])
        sys.exit(1)
    size = os.path.getsize(png) / 1024
    print("wrote %s (%.0f KB, %dx%d @2x)"
          % (os.path.relpath(png, ROOT), size, WIDTH, height))


if __name__ == "__main__":
    main()
