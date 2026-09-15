# Deployment

The page ships to two places, and they are not redundant.

| | URL | What it is | Language layer |
|---|---|---|---|
| **Vercel** | [https://blackout-desk-eight.vercel.app](https://blackout-desk-eight.vercel.app) | The public demo. A plain URL, no account, no sharing step. | No — points to the artifact |
| **Claude Artifact** | [`…/artifact/15681462…`](https://claude.ai/artifact/3eKJskZZThj72zRwZjBpK2) | The full product, including "Ask the desk" | Yes, via the `sample` runtime capability |

## Why both

The artifact is the complete product: the `sample` capability is what makes the
desk answerable in natural language, and that runtime exists nowhere else.

But an artifact is private until it is shared, and even shared it asks a judge
to be signed in. For a track whose validity gate is an **accessible demo**, that
is friction we do not need. The Vercel URL removes it entirely — anyone opens it,
nothing is asked of them, and every measurement is there.

That split only works because the page was built static-first from the
beginning. Nothing on it depends on the LLM; the conversational layer was always
an addition. On the static host the "Ask the desk" panel says so and links to the
artifact, rather than silently vanishing.

## How the two builds differ

One template, two outputs, from `python scripts/build_page.py`:

- `web/desk.html` — a **fragment**. The artifact runtime wraps it in a document,
  supplying doctype, charset, viewport, `color-scheme` and a small reset.
- `public/index.html` — a **complete document**, because a static host supplies
  none of that. The shell reproduces exactly what the runtime provides and
  nothing more, so the two stay visually identical.

Getting this backwards fails silently in both directions: a fragment on a static
host renders with no charset (every em-dash and ± in the copy breaks) and no
viewport (a phone lays it out at desktop width). `tests/test_deploy.py` pins it.

Deployed at **https://blackout-desk-eight.vercel.app**, from `main`.

> Vercel builds the repository's **production branch**, which defaults to `main`.
> The first deploy 404'd because all the work sat on a feature branch while
> `main` was still the initial commit. `main` is now the canonical branch.

## First deploy

The page is committed already, so there is no build container and nothing to
install — Vercel serves `public/` as static files.

**Dashboard:** New Project → import this repository → it reads `vercel.json` and
needs no further configuration. Leave the framework preset as *Other*.

**CLI:**

```bash
npx vercel          # preview deployment
npx vercel --prod   # production
```

`vercel.json` sets `outputDirectory: public`, `buildCommand: null`, and the
security headers, including a CSP that permits Google Fonts. A CSP that blocks
the font host fails silently — the type system just falls back — so
`tests/test_deploy.py` checks the policy against what the page actually loads.

## After any data refresh

Both builds and both hosts need updating, and only one of them is automatic:

1. `python -m blackout.build && python scripts/build_page.py`
2. Fix any prose `test_doc_figures` flags
3. Commit and push → **Vercel redeploys on its own**
4. **Republish the artifact by hand** — nothing can automate that, and it will
   keep serving the old numbers until someone does

Step 4 is the one that gets forgotten.
