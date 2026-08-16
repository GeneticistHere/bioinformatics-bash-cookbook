#!/usr/bin/env python3
"""Build the LinkedIn carousel: assets/carousel.pdf.

Twelve 1080x1350 pages (cover, ten traps, closing), one trap per page, set at
a size that stays readable when the feed scales the document down. Built from
the same HERO list as the README and the cheat sheet.

    python3 scripts/make_carousel.py

Needs Chrome to rasterise. The HTML is written either way.
"""

import html
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from recipes import HERO, RECIPES, SLIDE_TITLES, get   # noqa: E402

ASSETS = os.path.join(ROOT, "assets")
HANDLE = "github.com/GeneticistHere/bioinformatics-bash-cookbook"

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
]

CSS = """
@page { size: 1080px 1350px; margin: 0; }
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { background: #ffffff; }
body {
  font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
  color: #111111;
}
.page {
  width: 1080px; height: 1350px;
  padding: 84px 74px;
  display: flex; flex-direction: column;
  page-break-after: always; break-after: page;
  position: relative;
}
.page:last-child { page-break-after: auto; break-after: auto; }

/* cover */
.cover-kicker {
  font-family: "SF Mono", Menlo, monospace; font-size: 26px;
  color: #0072B2; letter-spacing: 0.5px; margin-bottom: 34px;
}
.cover h1 {
  font-size: 92px; line-height: 1.04; font-weight: 800;
  letter-spacing: -2px;
}
.cover .lede {
  font-size: 34px; line-height: 1.42; color: #3d3d3d; margin-top: 40px;
}
.spacer { flex: 1; }
.cover .foot {
  font-family: "SF Mono", Menlo, monospace; font-size: 23px; color: #6b6b6b;
}

/* trap pages */
.num {
  font-family: "SF Mono", Menlo, monospace; font-size: 27px;
  color: #9a9a9a; margin-bottom: 26px;
}
h2 {
  font-size: 62px; line-height: 1.1; font-weight: 800;
  letter-spacing: -1.2px; margin-bottom: 54px;
}
.block { margin-bottom: 40px; }
.tag {
  font-size: 23px; font-weight: 700; letter-spacing: 1.4px;
  text-transform: uppercase; margin-bottom: 14px;
}
.tag.bad  { color: #C0392B; }
.tag.good { color: #1E7A4C; }
.code {
  font-family: "SF Mono", Menlo, Consolas, monospace;
  font-size: 33px; line-height: 1.5;
  white-space: pre-wrap; word-break: break-word;
  padding: 22px 26px; border-radius: 8px;
  border-left: 7px solid transparent;
}
.code.bad  { background: #fbeceb; border-left-color: #C0392B; color: #8d2b20; }
.code.good { background: #e9f5ef; border-left-color: #1E7A4C; color: #15563a; }
.why {
  font-size: 33px; line-height: 1.46; color: #3d3d3d;
  border-top: 2px solid #e4e4e4; padding-top: 30px;
}
.rid {
  position: absolute; right: 78px; bottom: 62px;
  font-family: "SF Mono", Menlo, monospace; font-size: 21px; color: #b4b4b4;
}

/* closing */
.close h2 { font-size: 74px; margin-bottom: 46px; }
.close ul { list-style: none; font-size: 33px; line-height: 1.85; }
.close li:before { content: "\\2022"; color: #0072B2; margin-right: 18px; }
.close .repo {
  font-family: "SF Mono", Menlo, monospace; font-size: 27px;
  color: #0072B2; margin-top: 12px; word-break: break-all;
}
"""


def cover():
    return """<section class="page cover">
  <div class="cover-kicker">bioinformatics</div>
  <h1>Ten one-liners<br>that are<br>quietly wrong</h1>
  <div class="lede">Each one runs without an error and prints a plausible
    number.<br>The number is not what you think it is.</div>
  <div class="spacer"></div>
  <div class="foot">%s</div>
</section>""" % html.escape(HANDLE)


def trap_page(n, rid, wrong, right):
    r = get(rid)
    # markdown backticks are meaningless on a slide
    why = r["trap"].split(". ")[0].rstrip(".").replace("`", "") + "."
    return """<section class="page">
  <div class="num">%02d / 10</div>
  <h2>%s</h2>
  <div class="block">
    <div class="tag bad">&#10007; what people write</div>
    <div class="code bad">%s</div>
  </div>
  <div class="block">
    <div class="tag good">&#10003; what it should be</div>
    <div class="code good">%s</div>
  </div>
  <div class="spacer"></div>
  <div class="why">%s</div>
  <div class="rid">%s</div>
</section>""" % (n, html.escape(SLIDE_TITLES[rid]), html.escape(wrong),
                 html.escape(right), html.escape(why), rid)


def closing():
    n_traps = sum(1 for r in RECIPES if r.get("trap"))
    return """<section class="page close">
  <h2>All of it, tested.</h2>
  <ul>
    <li>%d command-line recipes</li>
    <li>%d documented traps</li>
    <li>A 300 KB toy genome, committed</li>
    <li>Every command run in CI on each push</li>
  </ul>
  <div class="spacer"></div>
  <div class="lede" style="font-size:30px">Clone it and every command in the
    README runs immediately. Nothing to download.</div>
  <div class="repo">%s</div>
</section>""" % (len(RECIPES), n_traps, html.escape(HANDLE))


def build_html():
    pages = [cover()]
    for n, (rid, wrong, right) in enumerate(HERO, 1):
        pages.append(trap_page(n, rid, wrong, right))
    pages.append(closing())
    return ("<!doctype html>\n<html><head><meta charset=\"utf-8\">"
            "<style>%s</style></head>\n<body>\n%s\n</body></html>\n"
            % (CSS, "\n".join(pages)))


def find_chrome():
    for path in CHROME_CANDIDATES:
        if path and os.path.exists(path):
            return path
    return None


def main():
    os.makedirs(ASSETS, exist_ok=True)
    page = os.path.join(ASSETS, "carousel.html")
    pdf = os.path.join(ASSETS, "carousel.pdf")

    with open(page, "w") as fh:
        fh.write(build_html())
    print("wrote", os.path.relpath(page, ROOT))

    chrome = find_chrome()
    if not chrome:
        print("Chrome not found - open the HTML and print to PDF at "
              "1080x1350 with margins off")
        return

    proc = subprocess.run(
        [chrome, "--headless=new", "--disable-gpu",
         "--no-pdf-header-footer", "--print-to-pdf-no-header",
         "--virtual-time-budget=4000",
         "--print-to-pdf=" + pdf, "file://" + page],
        capture_output=True, text=True)
    if not os.path.exists(pdf):
        print("PDF render failed:\n" + proc.stderr[-800:])
        sys.exit(1)
    print("wrote %s (%.0f KB, %d pages)"
          % (os.path.relpath(pdf, ROOT), os.path.getsize(pdf) / 1024,
             len(HERO) + 2))


if __name__ == "__main__":
    main()
