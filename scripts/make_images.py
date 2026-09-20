"""Render the share card and the touch icon from the mark.

Both are binaries that live in `public/`, and binaries in a repository rot: a
hand-made PNG cannot be re-derived when the palette or the wording moves. So
they are generated here from the same tokens and the same glyph the page uses,
and regenerating is one command.

    python scripts/make_images.py

Needs a Chrome or Edge install to rasterise; it is a one-off generator, not part
of the suite, and CI never runs it. If no browser is found it says so and exits
rather than leaving a half-written file.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
ICON = PUBLIC / "icon.svg"

VOID, GROUND, INK, MUTED, LIT = "#07090D", "#171F2A", "#E8ECF2", "#94A1B2", "#E8A33D"
OPEN, HALF = "#C9D8E8", "#5D7086"

CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def find_browser() -> str | None:
    for name in ("google-chrome", "chromium", "chrome", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    return next((c for c in CANDIDATES if Path(c).exists()), None)


def lanes_svg(scale: float = 1.0) -> str:
    """The mark's three lanes, at an arbitrary scale."""
    return ICON.read_text(encoding="utf-8")


CARD = f"""<!doctype html><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Instrument+Serif&family=Archivo:wght@400;500&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
  *{{box-sizing:border-box}}
  html,body{{margin:0;padding:0}}
  body{{width:1200px;height:630px;background:{VOID};overflow:hidden;
        font-family:Archivo,system-ui,sans-serif;color:{INK};position:relative}}
  .pad{{padding:60px 72px 138px;height:100%;display:flex;flex-direction:column;
        justify-content:space-between;position:relative;z-index:2}}
  .top{{display:flex;align-items:center;gap:26px}}
  .top svg{{width:86px;height:86px;display:block}}
  h1{{font-family:"Instrument Serif",Georgia,serif;font-size:82px;font-weight:400;
      letter-spacing:-.025em;margin:0;line-height:1}}
  .eyebrow{{font-family:"IBM Plex Mono",monospace;font-size:17px;letter-spacing:.16em;
            text-transform:uppercase;color:{MUTED};margin-bottom:16px}}
  .thesis{{font-family:"Instrument Serif",Georgia,serif;font-size:46px;font-style:italic;
           line-height:1.18;max-width:30ch;margin:0}}
  .thesis em{{font-style:normal;color:{LIT}}}
  .foot{{display:flex;align-items:baseline;justify-content:space-between;
         font-family:"IBM Plex Mono",monospace;font-size:18px;color:{MUTED};
         letter-spacing:.04em}}
  /* The week strip itself, full bleed along the bottom: two lanes that stop and
     one that does not, which is the same statement the mark makes. */
  .strip{{position:absolute;left:0;right:0;bottom:30px;z-index:1;
          display:flex;flex-direction:column;gap:9px;opacity:.95}}
  .lane{{display:flex;gap:7px;height:13px}}
  .lane i{{display:block;height:100%;border-radius:7px}}
  .l1 i{{background:{OPEN};opacity:.32}}
  .l2 i{{background:{HALF}}}
  .l3 i{{background:{LIT}}}
  .glow{{position:absolute;left:0;right:0;bottom:-70px;height:200px;z-index:0;
         background:radial-gradient(60% 100% at 50% 100%,
           color-mix(in srgb,{LIT} 22%,transparent) 0%, transparent 72%)}}
</style>
<div class="glow"></div>
<div class="strip">
  <div class="lane l1">{"".join(f'<i style="width:{w}px"></i>' for w in (150, 96, 150, 96, 150, 96, 150))}</div>
  <div class="lane l2">{"".join(f'<i style="width:{w}px"></i>' for w in (330, 300, 330))}</div>
  <div class="lane l3"><i style="width:1200px"></i></div>
</div>
<div class="pad">
  <div>
    <div class="eyebrow">Closure-window risk</div>
    <div class="top">{{mark}}<h1>Blackout Desk</h1></div>
  </div>
  <p class="thesis">For 49 hours each weekend, one venue on earth quotes your
    tokenized US stock. That premium is <em>not</em> free money.</p>
  <div class="foot">
    <span>blackout-desk-eight.vercel.app</span>
    <span>28 weekend blackouts measured</span>
  </div>
</div>
"""

TOUCH = """<!doctype html><meta charset="utf-8">
<style>html,body{{margin:0;padding:0;width:180px;height:180px;overflow:hidden}}
svg{{display:block;width:180px;height:180px}}</style>{mark}
"""


def shoot(browser: str, html: str, out: Path, width: int, height: int) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "card.html"
        page.write_text(html, encoding="utf-8")
        subprocess.run(
            [browser, "--headless", "--disable-gpu", "--hide-scrollbars",
             "--force-device-scale-factor=1", "--virtual-time-budget=6000",
             f"--window-size={width},{height}",
             f"--screenshot={out}", page.as_uri()],
            capture_output=True, check=False,
        )
    if not out.exists():
        raise SystemExit(f"{browser} produced no {out.name}")
    print(f"  wrote {out.relative_to(ROOT)}  ({out.stat().st_size / 1024:.0f} KB)")


def main() -> int:
    if not ICON.exists():
        raise SystemExit(f"{ICON.relative_to(ROOT)} is missing; the mark is the source")

    browser = find_browser()
    if not browser:
        print("No Chrome or Edge found. Both images are committed, so this is only")
        print("needed when the mark or the wording changes.")
        return 1

    mark = ICON.read_text(encoding="utf-8")
    print(f"Rendering with {browser}\n")
    shoot(browser, CARD.replace("{mark}", mark), PUBLIC / "og.png", 1200, 630)
    shoot(browser, TOUCH.format(mark=mark), PUBLIC / "icon-180.png", 180, 180)
    print("\nBoth are referenced from the document shell in scripts/build_page.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
