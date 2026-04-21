from __future__ import annotations

import json
import shutil
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
SOURCE_FILE = BASE_DIR / "weekly_source.json"
TARGET_FILE = BASE_DIR / "leaderboard_7_days.json"
BACKUP_FILE = BASE_DIR / "leaderboard_7_days.backup.json"


def load_source_payload() -> dict:
    if not SOURCE_FILE.exists():
        raise SystemExit(f"Missing source file: {SOURCE_FILE.name}")

    try:
        payload = json.loads(SOURCE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"weekly_source.json is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise SystemExit("weekly_source.json must contain a JSON object.")

    data = payload.get("data")
    if not isinstance(data, list):
        raise SystemExit("weekly_source.json must contain a `data` array.")
    if not data:
        raise SystemExit(
            "weekly_source.json has an empty `data` array. "
            "Refusing to overwrite leaderboard_7_days.json."
        )

    pagination = payload.get("pagination")
    if pagination is None:
        payload["pagination"] = {"current_page": 1, "per_page": 7}
    elif not isinstance(pagination, dict):
        raise SystemExit("`pagination` must be an object if provided.")

    payload["success"] = True
    return payload


def normalize_payload(payload: dict) -> dict:
    normalized_entries = []

    for index, entry in enumerate(payload["data"], start=1):
        if not isinstance(entry, dict):
            raise SystemExit(f"Entry {index} in `data` is not an object.")

        username = str(entry.get("username", "")).strip()
        avatar = str(entry.get("avatar", "")).strip()
        steamid64 = str(entry.get("steamid64", "")).strip()

        if not username:
            raise SystemExit(f"Entry {index} is missing `username`.")
        if not avatar:
            raise SystemExit(f"Entry {index} is missing `avatar`.")
        if not steamid64:
            raise SystemExit(f"Entry {index} is missing `steamid64`.")

        normalized_entries.append(
            {
                "username": username,
                "avatar": avatar,
                "steamid64": steamid64,
                "deposited": float(entry.get("deposited", 0) or 0),
                "wagered": float(entry.get("wagered", 0) or 0),
                "comission": float(entry.get("comission", 0) or 0),
                "status": int(entry.get("status", 0) or 0),
            }
        )

    return {
        "success": True,
        "data": normalized_entries,
        "pagination": payload.get("pagination", {"current_page": 1, "per_page": 7}),
    }


def main() -> None:
    payload = normalize_payload(load_source_payload())

    if TARGET_FILE.exists():
        shutil.copyfile(TARGET_FILE, BACKUP_FILE)

    TARGET_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print("Weekly leaderboard updated.")
    print(f"Source: {SOURCE_FILE.name}")
    print(f"Target: {TARGET_FILE.name}")
    print(f"Entries: {len(payload['data'])}")
    if BACKUP_FILE.exists():
        print(f"Backup: {BACKUP_FILE.name}")


if __name__ == "__main__":
    main()
