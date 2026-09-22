# tour-afterglow

Public GitHub Pages site: a mobile map of shopping spots for the free time after each day of a
5-day Kyushu group tour. Static, no build step. Pushing to `main` deploys `site/` via
`.github/workflows/pages.yml`.

## Privacy rules (the site is public — never break these)
- Never put hotel names, exact hotel positions, trip dates, flight numbers, or people's names in
  anything under `site/`, in commit messages, or in PR text. Days are only "Day1…Day5".
  The deploy workflow greps site/ for the regex in the `PRIVATE_WORDS` repo secret and fails the build on a match.
- Hotels appear only as "DayN 據點" at the nearest road intersection (`kind: "base"` in `pois.geojson`).
- The trip start date exists only in `site/js/days.js` (`TRIP.start`) for auto-selecting the day; never render it.
- Never commit `key.env`, `0.Reference/` (the tour PDF), or `data/raw/` (they are in `.gitignore`).

## Layout
- `site/index.html`, `site/css/tokens.css` (design tokens), `site/css/app.css`, `site/js/days.js` (per-day title/area/bounds), `site/js/app.js` (MapLibre GL JS app).
- Basemaps: OSM raster, GSI optimal vector tiles in 標準 and 淡色 styles (PMTiles; styles pinned in `site/data/gsi_std.json` from gsi-cyberjapan/optimal_bvmap and `site/data/gsi_pale.json` from gsi-cyberjapan/3dpc-3dtiles, glyphs/sprite from gsi-cyberjapan.github.io), GSI aerial photo raster. GSI annotations can be switched off by group — the groups (`ANNO_GROUPS` in `app.js`) are lists of `vt_code` from GSI's 注記分類コード table (https://maps.gsi.go.jp/help/pdf/vector/optbv_featurecodes.pdf).
- `site/data/*.geojson` — public data the page loads:
  - `pois.geojson` — sights/stations/malls + base intersections. props: `id, name, kind (sight|station|mall|airport|base), days[], gmaps_url?`
  - `uncertain.geojson` — places whose location is unknown, drawn as dashed circles. props: `name, days[], radius_m, note`
  - `routes.geojson` — OSRM coach-route estimates. props: `day, seq, from, to, distance_km, duration_min`
  - `shops.geojson` — Google Places shops. props: `id (place_id), name (zh-TW), name_ja, category, days[], area, rating, user_ratings_total, gmaps_url`
    - `category` ∈ `otaku, drugstore, restaurant, izakaya, supermarket, electronics, lifestyle, clothing`
    - `gmaps_url` = `https://www.google.com/maps/search/?api=1&query=<name>&query_place_id=<place_id>` (opens the Google Maps app on phones)
  - `transit.geojson` — bus/tram lines (MultiLineString). props: `days[], to, mode (bus|tram), ref, name, operator, headway_min|null`
- `scripts/` — Python (stdlib + certifi) data pipeline, run locally with the key in `key.env`:
  `geocode_pois.py` → `build_itinerary.py` → `route_osrm.py` → `fetch_places.py` → `translate_names.py` → `fetch_transit.py`.
  Shop names shown are Traditional Chinese (`name`); the Japanese original is `name_ja`. Fix a translation in `scripts/name_zh_overrides.json` (place_id → name) or directly in `shops.geojson`.
  They need `data/raw/*_private.json`, which exist only on the owner's PC.

## Editing from the phone (Claude app / claude.ai/code)
- Small changes: edit `site/**` directly — e.g. add a shop by appending a Feature to `shops.geojson`
  with the schema above (look up place_id/rating only if you can; otherwise omit `rating` and use a
  Google Maps search URL), mark a place as confirmed by moving it from `uncertain.geojson` to `pois.geojson`.
- Keep GeoJSON valid (check with `python -m json.tool site/data/<file>.geojson`).
- Commit to `main` and push; Pages redeploys automatically (~1 min).
- Re-running the Places search in the cloud: the manual workflow `refresh-places.yml` (needs repo secrets).
