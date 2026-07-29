# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running

```powershell
python main.py             # consola (menú de texto)
python app_gui.py          # interfaz gráfica Tkinter (ventana de escritorio)
uvicorn api:app --reload   # dashboard web en http://127.0.0.1:8000
```

Three front-ends over **two independent backends**:
- `main.py` — interactive console application (numbered menu loop in `main()`).
- `app_gui.py` — Tkinter desktop GUI (dark theme) that imports `HotelManager`,
  `matches`, and date helpers from `main.py` and reuses the exact business logic.
  Launch detached with `pythonw.exe app_gui.py` to avoid a console window.
- `index.html` served by `api.py` — web dashboard backed by Supabase. See
  **Web deployment** below.

The first two share `data.json` and `HotelManager`, so changes in one are visible in
the other on next load; they need nothing beyond the standard library (Tkinter ships
with CPython on Windows). The web dashboard shares **neither**: it reimplements the
logic in JavaScript and keeps its state in Supabase. Only `api.py` has dependencies
(`requirements.txt`). No build step, no test suite.

Running `uvicorn` locally still needs the four environment variables listed under
**Web deployment** — it will refuse to boot without them.

To exercise it non-interactively, redirect a UTF-8 input file via `cmd` (PowerShell
pipes text as UTF-16, which Python misreads on stdin):

```powershell
$env:PYTHONIOENCODING="utf-8"
cmd /c "python main.py < input.txt"
```

For unit-style checks, import `HotelManager` directly, call its methods, and
re-instantiate to test persistence.

## What this is

A management system for **Aparthotel Paros** — a 100-apartment building (10 floors
× 10 units). The console app is a functional port of the web dashboard `index.html`
(a self-contained HTML/CSS/JS single-page app; all its JavaScript lives in one IIFE
that opens at line 482 and closes at the end of the file). Both implement the same
data model, but their backup formats have since **diverged** — see Architecture — so
exports are no longer freely interchangeable.

`index.html` no longer uses `localStorage`; it loads and saves through `api.py` (the
leftover `STORAGE_KEY` constant is unused). Opening the file directly from disk now
shows generated sample data and a "sin conexión" warning, because every `fetch`
fails — to see real data you must go through the server.

## Architecture

- `models.py` — the `Room` dataclass plus per-type configuration dicts
  (`BEDROOMS_BY_TYPE`, `TYPE_SHORT`, `TYPE_LABEL`, `AREA_BY_TYPE`, `PRICE_BY_TYPE`,
  keyed by `'standard' | 'suite' | 'vip'`) and format helpers (`currency`,
  `format_date`, `normalize_text`). `Room.to_dict`/`from_dict` use **camelCase keys**
  (`checkinDate`, `checkoutDate`) on purpose — that's the web app's format, and
  matching it is what keeps room objects readable by both sides. Don't rename them
  to snake_case.
- `main.py` — `HotelManager` owns all state (`rooms`, `history`, `total_revenue`,
  `guest_history`) and operations; module-level functions render the menu views.
- `api.py` — FastAPI backend for the web dashboard. HTTP Basic auth on every route
  that touches hotel data, serves `index.html` at `/`, and stores the entire state
  as one JSON blob in Supabase (table `hotel_data`, always row `id = 1`). It does
  **not** import `HotelManager` and never touches `data.json`.

Key structural facts to know before editing:

- **Apartment generation** (`HotelManager._generate_departments`) mirrors the web
  app's `generarDepartamentos` exactly: number = `floor*100 + i` for floors 1–10,
  type cycles by `(i-1) % 3`, and units `i == 3` and `i == 7` seed as occupied with
  sample guests/dates derived from `date.today()`. If you change this, change the JS
  in `index.html` too, or the two apps will diverge.
- **Persistence**: `data.json` next to the scripts, written via `_save()` after every
  mutating operation. Its top-level shape is the web backup format:
  `{rooms, history, totalRevenue, guestHistory}`. `_load()` returns `False` (→ fresh
  generation) when the file is missing, unreadable, or has an empty `rooms` list.
  Note `rooms` must be a JSON **array**; an older single-file format keyed rooms by
  number — those files are incompatible and should be deleted, not migrated.
- **Two parallel stores, as in the source app**: live occupancy lives on each `Room`
  (`status`, `guest`, `checkin_date`, `checkout_date`); `history` is an append-only
  billing log written at check-out; `guest_history` is a per-guest stay index keyed
  by lowercased name (capped at 20 entries each). Revenue accrues only at check-out.
- **Dates** are ISO `'YYYY-MM-DD'` strings everywhere; `nights = (checkout - checkin).days`.
  `today()` uses the real system clock.
- **`data.json` and the web store have diverged in their fourth key.** `data.json` holds
  `{rooms, history, totalRevenue, guestHistory}`; the web app saves
  `{rooms, history, totalRevenue, operationalTasks}`. Neither side knows the other's
  key, so copying a backup across silently drops it. Either keep them separate or
  port both stores properly — don't half-merge them.
- **API contract**: `GET /api/state` returns the full state object with per-key
  defaults; `POST /api/update` takes the same shape and rejects an empty `rooms`
  list with 422, so a malformed request can't wipe the hotel. If you add a key to
  the web state, add it to the `HotelState` model in `api.py` too — Pydantic drops
  undeclared keys on save, silently.

## Web deployment (Render)

Four environment variables, all required. If any is missing or malformed, `api.py`
prints a labelled `ERROR CRITICO` block to stderr — naming the variable and the fix —
and stops the process with exit code 1:

- `SUPABASE_URL` / `SUPABASE_KEY` — project URL and the API key whose RLS policy
  allows read/write on `hotel_data`.
- `APP_USER` / `APP_PASSWORD` — HTTP Basic credentials for the dashboard.

There is no `Procfile` or `render.yaml`; the start command lives in the Render
dashboard:

```
uvicorn api:app --host 0.0.0.0 --port $PORT
```

Three things that fail in confusing ways:

- **Basic auth credentials must be ASCII.** FastAPI decodes them as ASCII
  (`fastapi/security/http.py`, `b64decode(param).decode("ascii")`), so a password
  with `ñ` or a tilde yields a bare 401 no matter what it's compared against.
  `api.py` validates this at boot rather than letting you debug an impossible login.
- **`requirements.txt` must be UTF-8.** PowerShell's `>` and `Out-File` default to
  UTF-16, which pip cannot read, so the deploy dies before running any code. Write
  it with `Out-File -Encoding utf8` and check the file has no null bytes. Note that
  overwriting the file in place can preserve the old UTF-16 encoding — delete it
  first if in doubt.
- **`_fatal()` uses `os._exit(1)`, not `sys.exit(1)`.** Boot checks run while
  uvicorn imports the module inside its event loop, so a `SystemExit` unwinds
  through asyncio and buries the message under ~30 lines of traceback. `os._exit`
  stops the process immediately; stderr is flushed by hand first. Don't swap it
  back for `sys.exit` or `raise`.
- **The route handlers are sync `def` on purpose.** The Supabase client is
  synchronous; declaring them `async def` would run that blocking I/O on the event
  loop and stall every other request. As plain `def`, FastAPI runs them in a
  threadpool. Don't "modernize" them.

`GET /health` is public and returns no hotel data, for Render's monitoring. So are
the three PWA routes (`/manifest.json`, `/service-worker.js`, `/icons/{name}`):
the browser fetches a manifest without credentials by default, and a service
worker that 401s on update stops updating silently. They carry no hotel data.
Everything else requires auth.

There is deliberately no `StaticFiles` mount, since mounting the project directory
would expose `data.json`, `api.py` and any `.env` file. Each servable file gets its
own explicit route instead, and `/icons/{name}` checks `name` against the
`ALLOWED_ICONS` allow-list rather than joining it onto a path — a join would let
`..%2f` climb out of the directory. Add files to that set, don't loosen the check.

## PWA

`index.html` is installable: `manifest.json` (name, icons, `start_url` `/`) plus
`service-worker.js`, registered at the end of the IIFE on `window.load`.

- **`start_url` is `/`, not `/index.html`** — `api.py` serves the app at the root
  and has no `/index.html` route, so that path would 404 on launch.
- **The worker never caches `/api/`.** Occupancy is live state; a cached hotel is
  worse than no hotel. The `fetch` handler returns early for those paths and for
  every non-GET request.
- **Navigation is stale-while-revalidate**: the page paints from cache instantly
  and the new version downloads behind it, so a Render deploy shows up on the next
  reload with nothing to bump by hand. Static assets and the two CDNs (Google
  Fonts, Font Awesome) are cache-first.
- Only `200` responses are cached — a cached `401` or `502` would wedge the app.
- `CACHE_VERSION` in `service-worker.js` names the cache; changing it drops every
  older cache on activate. `/service-worker.js` is served with `Cache-Control:
  no-cache` so the browser always revalidates the worker itself.
- `icons/` holds generated placeholders; `make_icons.py` rewrites them with the
  standard library (no Pillow). Replace the PNGs with a real logo and don't
  re-run it.

## Conventions

- All user-facing strings and prompts are in **Spanish**; code identifiers, methods,
  and comments are in English.
- Currency is CLP formatted as `$120.000` (dot thousands separator, no decimals).
