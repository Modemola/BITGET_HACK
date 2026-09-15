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

console.log(JSON.stringify(report, null, 1));
process.exit(0);
