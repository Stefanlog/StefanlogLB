# StefanlogLB Backend Setup

## 1. Create your local env file
Copy `backend.env.example` to `backend.env`.

## 2. Add your TF2Easy cookie
In Firefox/Chrome DevTools:
1. Open the `getReferredUsers` request.
2. Open `Headers`.
3. Find the `Cookie` request header.
4. Copy the full value only.
5. Paste it into:

```text
TF2EASY_COOKIE=your_cookie_here
```

## 3. Start the backend
If you want automatic live TF2Easy updates, install Playwright first:

```bat
install_playwright_backend.bat
```

On Windows, double-click `start_server.bat`

Or run:

```bash
python server.py
```

Optional env settings:

```text
HOST=0.0.0.0
PORT=8000
TF2EASY_CACHE_SECONDS=90
TF2EASY_FETCH_MODE=playwright
PLAYWRIGHT_BROWSER=chromium
PLAYWRIGHT_CHANNEL=
PLAYWRIGHT_EXECUTABLE_PATH=
PLAYWRIGHT_HEADLESS=1
PLAYWRIGHT_SETTLE_MS=2500
```

## 4. Open the site
Visit:

```text
http://127.0.0.1:8000
```

The backend will:
- serve your HTML/CSS/JS files
- proxy `GET /api/leaderboard` to TF2Easy using your cookie
- try a real Playwright browser session when `TF2EASY_FETCH_MODE=playwright`
- proxy the weekly board with `range=7`
- keep your cookie out of browser JavaScript
- cache live responses briefly so repeated page loads do not spam TF2Easy

## Notes
- If TF2Easy changes your cookie, update `backend.env`.
- If the proxy fails, the frontend falls back to the local weekly/all-time JSON files.
- For production hosting, bind with `HOST=0.0.0.0`.
- If Chromium install is not desired, you can try your local Edge/Chrome by setting:

```text
PLAYWRIGHT_CHANNEL=msedge
```

or set a direct browser binary path with `PLAYWRIGHT_EXECUTABLE_PATH`.

## Simpler weekly workflow
If live automation is blocked by Cloudflare, use the semi-automatic updater in [WEEKLY_UPDATE.md](WEEKLY_UPDATE.md):
- paste the raw `7 Days` JSON into `weekly_source.json`
- run `update_weekly_data.bat`
- refresh the site
