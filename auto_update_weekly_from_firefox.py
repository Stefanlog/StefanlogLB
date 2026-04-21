from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parent
API_URL = "https://www.tf2easy.com/api/proxy/myapi/affiliate/getReferredUsers?page=1&status=&sortField=wagered&sortOrder=desc&range=7"
SOURCE_FILE = BASE_DIR / "weekly_source.json"
TARGET_FILE = BASE_DIR / "leaderboard_7_days.json"
BACKUP_FILE = BASE_DIR / "leaderboard_7_days.backup.json"
LOG_FILE = BASE_DIR / "auto_update_weekly.log"


def log(message: str) -> None:
    from datetime import datetime

    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {message}"
    print(message)
    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(line + "\n")


def find_firefox_cookie_db() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise SystemExit("APPDATA environment variable was not found.")

    profiles_dir = Path(appdata) / "Mozilla" / "Firefox" / "Profiles"
    if not profiles_dir.exists():
        raise SystemExit(f"Firefox profiles folder not found: {profiles_dir}")

    candidates = sorted(
        profiles_dir.glob("*/cookies.sqlite"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not candidates:
        raise SystemExit("No Firefox cookies.sqlite file found.")

    return candidates[0]


def read_tf2easy_cookies(cookie_db: Path) -> dict[str, str]:
    with tempfile.TemporaryDirectory() as tmpdir:
        copied_db = Path(tmpdir) / "cookies.sqlite"
        shutil.copyfile(cookie_db, copied_db)

        connection = sqlite3.connect(copied_db)
        try:
            rows = connection.execute(
                """
                SELECT name, value
                FROM moz_cookies
                WHERE host LIKE '%tf2easy.com'
                """
            ).fetchall()
        finally:
            connection.close()

    cookies = {name: value for name, value in rows}
    required = ["cf_clearance", "XSRF-TOKEN", "laravel_session"]
    missing = [name for name in required if name not in cookies]

    if missing:
        raise SystemExit(
            "Missing TF2Easy cookies from Firefox: "
            + ", ".join(missing)
            + ". Log into TF2Easy in Firefox, then run again."
        )

    return cookies


def fetch_weekly_payload(cookies: dict[str, str]) -> dict:
    cookie_header = "; ".join(f"{name}={value}" for name, value in cookies.items())
    xsrf_token = unquote(cookies.get("XSRF-TOKEN", ""))

    request = Request(
        API_URL,
        headers={
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Cookie": cookie_header,
            "Referer": "https://www.tf2easy.com/affiliates",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) "
                "Gecko/20100101 Firefox/149.0"
            ),
            "X-XSRF-TOKEN": xsrf_token,
        },
    )

    try:
        with urlopen(request, timeout=30) as response:
            text = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"TF2Easy returned HTTP {exc.code}: {body[:180]}") from exc
    except URLError as exc:
        raise SystemExit(f"Could not reach TF2Easy: {exc.reason}") from exc

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"TF2Easy returned non-JSON content: {text[:180]}") from exc

    data = payload.get("data")
    if not isinstance(data, list):
        raise SystemExit("TF2Easy response did not contain a data array.")
    if not data:
        raise SystemExit("TF2Easy response had an empty data array. Refusing to overwrite.")

    payload["success"] = True
    return payload


def normalize_payload(payload: dict) -> dict:
    entries = []

    for entry in payload["data"]:
        entries.append(
            {
                "username": str(entry.get("username", "")).strip(),
                "avatar": str(entry.get("avatar", "")).strip(),
                "steamid64": str(entry.get("steamid64", "")).strip(),
                "deposited": float(entry.get("deposited", 0) or 0),
                "wagered": float(entry.get("wagered", 0) or 0),
                "comission": float(entry.get("comission", 0) or 0),
                "status": int(entry.get("status", 0) or 0),
            }
        )

    return {
        "success": True,
        "data": entries,
        "pagination": payload.get("pagination", {"current_page": 1, "per_page": 7}),
    }


def main() -> None:
    log("Starting Firefox-cookie weekly update.")
    cookie_db = find_firefox_cookie_db()
    log(f"Using Firefox cookie DB: {cookie_db}")
    cookies = read_tf2easy_cookies(cookie_db)
    log("Loaded TF2Easy cookies from Firefox.")
    payload = normalize_payload(fetch_weekly_payload(cookies))

    if TARGET_FILE.exists():
        shutil.copyfile(TARGET_FILE, BACKUP_FILE)

    text = json.dumps(payload, indent=2) + "\n"
    SOURCE_FILE.write_text(text, encoding="utf-8")
    TARGET_FILE.write_text(text, encoding="utf-8")

    first_entry = payload["data"][0]
    log(f"Weekly leaderboard updated. Entries={len(payload['data'])}.")
    log(f"First entry: {first_entry['username']}, wagered={first_entry['wagered']:.2f}")


if __name__ == "__main__":
    main()
