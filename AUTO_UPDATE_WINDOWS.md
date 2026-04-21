# Free Automatic Weekly Update

This uses your normal Firefox session instead of Playwright. It reads your local Firefox TF2Easy cookies, calls the weekly API, writes `weekly_source.json`, then updates `leaderboard_7_days.json`.

## Requirements
- Stay logged into TF2Easy in Firefox.
- Your PC must be awake.
- If Cloudflare asks for verification, solve it manually once in Firefox.

## Test Manually First
Double-click:

```text
auto_update_weekly_from_browser.bat
```

It should:
1. Read TF2Easy cookies from Firefox.
2. Call the TF2Easy `7 Days` API.
3. Save `weekly_source.json`.
4. Update `leaderboard_7_days.json`.

## Task Scheduler
1. Open `Task Scheduler`.
2. Click `Create Basic Task...`.
3. Name it `Stefanlog Weekly Browser Update`.
4. Choose `Daily`.
5. Finish the wizard.
6. Right-click the new task and open `Properties`.
7. Go to `Triggers`, edit the trigger, and enable `Repeat task every: 1 hour` for `Indefinitely`.
8. Go to `Actions`, edit the action.
9. Set `Program/script` to:

```text
C:\Users\Stefa\Downloads\leaderboard_site\leaderboard_site\auto_update_weekly_from_browser.bat
```

10. Set `Start in` to:

```text
C:\Users\Stefa\Downloads\leaderboard_site\leaderboard_site
```

## Important
This is free, but not perfect. It depends on your browser being logged in and Cloudflare not interrupting the page load.
