#!/usr/bin/env python3
"""Rebuild the generated sections of README.md from recipes.py.

The README has two generated blocks, each delimited by HTML comments:

    <!-- BEGIN TRAPS -->  ... <!-- END TRAPS -->
    <!-- BEGIN COOKBOOK --> ... <!-- END COOKBOOK -->

Everything outside them is hand-written and left untouched. Run this after
editing recipes.py:

    python3 scripts/render_readme.py          # rewrite README.md
    python3 scripts/render_readme.py --check  # fail if README is out of date
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from recipes import HERO, RECIPES, by_category, get   # noqa: E402

README = os.path.join(ROOT, "README.md")


def cell(text):
    """Escape a bash one-liner for use inside a markdown table cell."""
    return text.replace("|", "\\|").replace("\n", " ")


def render_traps():
    rows = ["| # | What people write | What it should be | Why |",
            "|---|-------------------|-------------------|-----|"]
    for n, (rid, wrong, right) in enumerate(HERO, 1):
        r = get(rid)
        # first sentence of the trap, kept short enough for a table cell
        summary = r["trap"].split(". ")[0].rstrip(".")
        rows.append("| %d | `%s` | `%s` | %s (`%s`) |"
                    % (n, cell(wrong), cell(right), summary, rid))
    return "\n".join(rows)


def render_cookbook():
    out = []
    for key, title, items in by_category():
        traps = [r for r in items if r.get("trap")]
        out.append("### %s" % title)
        out.append("")
        out.append("%d recipes, %d with traps." % (len(items), len(traps)))
        out.append("")
        out.append("| ID | Task | One-liner |")
        out.append("|----|------|-----------|")
        for r in items:
            mark = " &#9888;" if r.get("trap") else ""
            out.append("| `%s`%s | %s | `%s` |"
                       % (r["id"], mark, r["task"], cell(r["cmd"])))
        if traps:
            out.append("")
            out.append("<details><summary><b>&#9888; Traps in this section "
                       "(%d)</b></summary>" % len(traps))
            out.append("")
            for r in traps:
                out.append("- **`%s` %s**: %s"
                           % (r["id"], r["task"], r["trap"]))
            out.append("")
            out.append("</details>")
        out.append("")
    return "\n".join(out).rstrip()


def splice(text, name, body):
    begin, end = "<!-- BEGIN %s -->" % name, "<!-- END %s -->" % name
    pattern = re.compile(re.escape(begin) + ".*?" + re.escape(end), re.DOTALL)
    if not pattern.search(text):
        sys.exit("marker %s not found in README.md" % name)
    replacement = "%s\n\n%s\n\n%s" % (begin, body, end)
    # NB: pass a function, not a string. re.sub expands backslash escapes in a
    # replacement string, which would turn the \t and \n inside awk one-liners
    # into real tabs and newlines and break every table row containing them.
    return pattern.sub(lambda _: replacement, text)


def main():
    with open(README) as fh:
        original = fh.read()

    updated = splice(original, "TRAPS", render_traps())
    updated = splice(updated, "COOKBOOK", render_cookbook())

    if "--check" in sys.argv:
        if updated != original:
            sys.exit("README.md is out of date - run "
                     "python3 scripts/render_readme.py")
        print("README.md is up to date")
        return

    with open(README, "w") as fh:
        fh.write(updated)

    traps = sum(1 for r in RECIPES if r.get("trap"))
    print("README.md rebuilt: %d recipes, %d traps, %d highlighted"
          % (len(RECIPES), traps, len(HERO)))


if __name__ == "__main__":
    main()
