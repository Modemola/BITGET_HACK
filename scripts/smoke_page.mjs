/**
 * Load a built page in a real DOM and report what actually rendered.
 *
 * Static checks cannot catch the failure this exists for. On 2026-09-14 a
 * stripped backslash turned a JavaScript string literal into a syntax error:
 * the HTML still validated, every element was still in the markup, the tests
 * still passed - and the page shipped with both charts empty and every control
 * dead, because the entire script had failed to parse.
 *
 * Emits JSON so a test can assert on it.
 *
 *   node scripts/smoke_page.mjs public/index.html
 */

import fs from "node:fs";
import { JSDOM, VirtualConsole } from "jsdom";

const file = process.argv[2];
if (!file) {
  console.error("usage: node scripts/smoke_page.mjs <page.html>");
  process.exit(2);
}

const errors = [];
const virtualConsole = new VirtualConsole()
  .on("jsdomError", (e) => errors.push(e.message || String(e)))
  .on("error", (...args) => errors.push(args.join(" ")));

const dom = new JSDOM(fs.readFileSync(file, "utf8"), {
  runScripts: "dangerously",
  pretendToBeVisual: true,
  virtualConsole,
  url: "https://example.invalid/",
});

// The page draws on load; give its handlers a tick to run.
await new Promise((resolve) => setTimeout(resolve, 500));
const d = dom.window.document;

const count = (selector) => d.querySelectorAll(selector).length;

const report = {
  errors,
  charts: {
    timeline: count("#timeline > *"),
    drift: count("#drift-chart > *"),
  },
  panels: {
    evidence: count("#evidence > *"),
    analogues: count("#an-body > *"),
    hedges: count("#hedge-body > *"),
    exposure: count("#expo-bar > *"),
    calendar: count("#cal-strip > *"),
  },
  controls: {
    scrub: !!d.getElementById("scrub"),
    scrubTrackBands: count("#scrub-track i"),
    position: d.getElementById("position")?.value ?? null,
    sliders: count(".ctrl input[type=range]"),
  },
  // The beacon is CSS, but the class it hooks is emitted by drawTimeline. A
  // guard that only reads the stylesheet passes while nothing animates.
  beacon: {
    lanes: count(".lane-lit"),
    segments: count(".lane-lit rect"),
  },
  lattice: {
    cells: count(".lattice-cell"),
    inHeader: !!d.querySelector("header .lattice"),
    // The strip's own pointer target must never sit inside the lattice, or the
    // decoration would swallow the interaction it sits behind.
    swallowsStrip: !!d.querySelector(".lattice #tl-hit"),
  },
  // Magnitude bars: proportional, signed correctly, and inside their track.
  bars: (() => {
    const bad = [];
    for (const i of d.querySelectorAll(".dvbar i, .mbar i")) {
      const w = parseFloat(i.style.width);
      const cap = i.parentElement.classList.contains("dvbar") ? 50 : 100;
      if (!isFinite(w) || w < 0 || w > cap + 0.01) bad.push(i.style.width);
    }
    return {
      diverging: count(".dvbar i"),
      magnitude: count(".mbar i"),
      outOfTrack: bad,
      signsMatchValues: [...d.querySelectorAll("td .dvbar")].every((bar) => {
        const val = bar.parentElement.querySelector(".val")?.textContent ?? "";
        const negative = val.trim().startsWith("-");
        return bar.querySelector("i").classList.contains(negative ? "neg" : "pos");
      }),
    };
  })(),
  sectionNumbers: count(".sec-n"),
  tools: count(".tools a"),
  deadLinks: [...d.querySelectorAll('.tools a[href^="#"]')]
    .filter((a) => !d.querySelector(a.getAttribute("href")))
    .map((a) => a.getAttribute("href")),
  answers: count("#ask details"),
  live: {
    regime: d.getElementById("regime-label")?.textContent ?? null,
    countdown: d.getElementById("countdown")?.textContent?.trim() ?? null,
    regimeStamp: d.documentElement.getAttribute("data-regime"),
  },
};

// Interactions, exercised rather than merely present. A handler that throws
// leaves the markup intact and every static check green.
function fire(sel, type, x) {
  const el = d.querySelector(sel);
  if (!el) return false;
  el.dispatchEvent(new dom.window.MouseEvent(type, { clientX: x, clientY: 80, bubbles: true }));
  return true;
}

report.interactions = {};
try {
  fire("#tl-hit", "pointermove", 420);
  const tip = d.getElementById("tl-tip");
  report.interactions.stripHover = {
    cursorShown: d.querySelector("#tl-cursor")?.getAttribute("opacity") === "1",
    tipShown: tip ? !tip.hidden : false,
    regimeNamed: !/outside the calendar/.test(tip?.textContent ?? ""),
  };

  fire("#dr-hit", "pointermove", 360);
  const dtip = d.getElementById("dr-tip");
  report.interactions.driftHover = {
    tipShown: dtip ? !dtip.hidden : false,
    quotesQuantiles: /median/.test(dtip?.textContent ?? ""),
  };

  const before = d.getElementById("scrub")?.value;
  fire("#tl-hit", "click", 640);
  report.interactions.clickToScrub =
    before !== undefined && before !== d.getElementById("scrub")?.value;

  const pos = d.getElementById("position");
  if (pos) {
    pos.value = "1,000,000";
    pos.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
    report.interactions.positionRecomputes =
      /\$1,000,000|\$8,/.test(d.getElementById("expo-caption")?.textContent ?? "") ||
      d.getElementById("expo-caption")?.classList.contains("flash") === true;
  }
} catch (e) {
  report.interactions.error = e.message;
}
report.errors = errors;

console.log(JSON.stringify(report, null, 1));
process.exit(0);
