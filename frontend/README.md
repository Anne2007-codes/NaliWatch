# NaliWatch frontend

Static, no-build frontend for the NaliWatch septic-waste tracking plan (Part 1 + Part 2).

Run: open `index.html`, or `npm start` to serve it locally.
All data is mock and lives in memory (`js/data.js`); it resets on reload.

## Structure
```
index.html          page shell and script order
css/styles.css      water theme, layout, components
js/core.js          state and helpers
js/i18n.js          English / Hindi labels
js/data.js          mock ward data, scoring, estimator
js/ui.js            nav, sidebar, toast, classifier
js/views/           one file per screen
  landing, household, report, asha, bot, officer,
  operator, driver, plant, flags, admin, public
js/app.js           login, route table, router
```
Demo: any 4-digit sign-in code; driver pick-up code is 1234.

## Demo build additions
- `js/demo.js` guided 10-step tour (landing page button, or open `index.html?demo=1`)
- `js/ai.js` AI result card, sample photos, analysing animation (mock of the Claude vision call)
- `js/map.js` MapLibre + OpenStreetMap map (vendored in `js/vendor/`), animated tanker, trail, health overlay
- `js/receipt.js` verified-drop receipt with QR and timeline
- `css/extra.css` styles for all of the above
- `js/data.js` is seeded with 24 tanks, 8 reports, 7 trips and 3 flags so no screen is empty
The map needs internet for OSM tiles; markers, zones and the trip animation still work offline.

## Next step
Replace `js/data.js` with API calls (FastAPI) and the SVG map with MapLibre when moving to the Next.js stack in the plan.
