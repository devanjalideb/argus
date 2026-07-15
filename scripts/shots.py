"""Screenshot-diff helper: capture each screen at 1536px into design-review/.

Usage (venv python):  python scripts/shots.py [screen-name ...]
No args = all screens.  Server must be running on http://localhost:8000.
"""
from __future__ import annotations

import pathlib
import sys

from playwright.sync_api import sync_playwright

OUT = pathlib.Path(__file__).resolve().parents[1] / "design-review"
OUT.mkdir(exist_ok=True)

SCREENS = {
    "command-center": "/",
    "watchtower": "/watchtower",
    "blast-radius": "/blast-radius",
    "risk-memory": "/risk-memory",
    "knowledge-graph": "/knowledge-graph",
    "entity-explorer": "/entity-explorer",
    "reports": "/reports",
    "integrations": "/integrations",
    "case-management": "/case-management",
    "settings": "/settings",
}

targets = [a for a in sys.argv[1:] if a in SCREENS] or list(SCREENS)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1536, "height": 1024}, device_scale_factor=1)
    for name in targets:
        page.goto("http://localhost:8000" + SCREENS[name], wait_until="networkidle")
        page.wait_for_timeout(1400)
        path = OUT / f"{name}.png"
        page.screenshot(path=str(path), full_page=True)
        print("saved", path.name)
    browser.close()
