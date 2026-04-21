# Weekly Update

## Fast workflow
1. Open TF2Easy affiliates in your normal browser.
2. In DevTools, copy the raw `7 Days` JSON response from `getReferredUsers`.
3. Paste that JSON into `weekly_source.json` and save it.
4. Double-click `update_weekly_data.bat`
5. Refresh `leaderboards.html`

## What it updates
- `leaderboard_7_days.json`

## Safety
- The previous weekly file is copied to `leaderboard_7_days.backup.json` before overwrite.
- The updater refuses to overwrite the weekly board if `weekly_source.json` has an empty `data` array.

## More Automatic
For the free browser-copy automation, see `AUTO_UPDATE_WINDOWS.md`.
