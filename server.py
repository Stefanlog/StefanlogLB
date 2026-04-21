from __future__ import annotations

import json
import os
import time
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlencode, urlparse
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / "backend.env"
DEFAULT_API_URL = "https://www.tf2easy.com/api/proxy/myapi/affiliate/getReferredUsers"
CACHE: dict[str, dict] = {}


def load_env_file() -> None:
    if not ENV_PATH.exists():
        return

    for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def read_local_leaderboard(range_value: str) -> dict:
    if range_value == "7":
        filename = "leaderboard_7_days.json"
    elif range_value == "30":
        filename = "leaderboard_30_days.json"
    else:
        filename = "leaderboard_all_time.json"
    local_file = BASE_DIR / filename
    if not local_file.exists():
        return {"success": False, "error": f"Local {filename} not found", "data": []}
    return json.loads(local_file.read_text(encoding="utf-8"))


def get_tf2easy_cookie() -> str:
    cookie = os.getenv("TF2EASY_COOKIE", "").strip()
    if not cookie:
        raise RuntimeError("Missing TF2EASY_COOKIE in backend.env or environment")
    return cookie


def extract_xsrf_token(cookie: str) -> str:
    for cookie_part in cookie.split(";"):
        part = cookie_part.strip()
        if part.startswith("XSRF-TOKEN="):
            return unquote(part.split("=", 1)[1])
    return ""


def build_tf2easy_headers() -> dict:
    cookie = get_tf2easy_cookie()
    xsrf_token = extract_xsrf_token(cookie)

    headers = {
        "Cookie": cookie,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.tf2easy.com/affiliates",
        "Origin": "https://www.tf2easy.com",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
    }

    if xsrf_token:
        headers["X-XSRF-TOKEN"] = xsrf_token

    return headers


def build_playwright_cookies() -> list[dict[str, Any]]:
    cookie = get_tf2easy_cookie()
    cookie_domain = os.getenv("TF2EASY_COOKIE_DOMAIN", ".tf2easy.com")
    cookies: list[dict[str, Any]] = []

    for cookie_part in cookie.split(";"):
        part = cookie_part.strip()
        if "=" not in part:
            continue

        name, value = part.split("=", 1)
        cookies.append(
            {
                "name": name,
                "value": value,
                "domain": cookie_domain,
                "path": "/",
                "secure": True,
                "sameSite": "Lax",
                "httpOnly": name in {"laravel_session"},
            }
        )

    return cookies


def fetch_remote_page_http(query_params: dict[str, str]) -> dict:
    api_url = os.getenv("TF2EASY_API_URL", DEFAULT_API_URL)
    remote_url = f"{api_url}?{urlencode(query_params)}"
    request = Request(
        remote_url,
        headers=build_tf2easy_headers(),
    )

    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_remote_page_playwright(query_params: dict[str, str]) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - depends on local machine setup
        raise RuntimeError(
            "Playwright is not installed. Run install_playwright_backend.bat or "
            "`python -m pip install playwright` then `python -m playwright install chromium`."
        ) from exc

    api_url = os.getenv("TF2EASY_API_URL", DEFAULT_API_URL)
    xsrf_token = extract_xsrf_token(get_tf2easy_cookie())
    settle_ms = int(os.getenv("PLAYWRIGHT_SETTLE_MS", "2500"))
    browser_name = os.getenv("PLAYWRIGHT_BROWSER", "chromium").strip().lower()
    browser_channel = os.getenv("PLAYWRIGHT_CHANNEL", "").strip() or None
    executable_path = os.getenv("PLAYWRIGHT_EXECUTABLE_PATH", "").strip() or None
    headless = os.getenv("PLAYWRIGHT_HEADLESS", "1").strip() != "0"
    user_data_dir = os.getenv("PLAYWRIGHT_USER_DATA_DIR", "").strip() or None
    login_wait_seconds = int(os.getenv("PLAYWRIGHT_LOGIN_WAIT_SECONDS", "0"))

    with sync_playwright() as playwright:
        browser_type = getattr(playwright, browser_name, None)
        if browser_type is None:
            raise RuntimeError(f"Unsupported PLAYWRIGHT_BROWSER `{browser_name}`")

        launch_kwargs: dict[str, Any] = {"headless": headless}
        if browser_channel:
            launch_kwargs["channel"] = browser_channel
        if executable_path:
            launch_kwargs["executable_path"] = executable_path

        browser = None
        context = None
        try:
            if user_data_dir:
                context = browser_type.launch_persistent_context(user_data_dir, **launch_kwargs)
            else:
                browser = browser_type.launch(**launch_kwargs)
                context = browser.new_context()
                context.add_cookies(build_playwright_cookies())

            page = context.pages[0] if context.pages else context.new_page()
            page.goto("https://www.tf2easy.com/affiliates", wait_until="domcontentloaded", timeout=60000)
            if user_data_dir and not headless and login_wait_seconds > 0:
                page.wait_for_timeout(login_wait_seconds * 1000)
            if settle_ms > 0:
                page.wait_for_timeout(settle_ms)

            response_payload = page.evaluate(
                """
                async ({ apiUrl, params, xsrfToken }) => {
                  const url = `${apiUrl}?${new URLSearchParams(params).toString()}`;
                  const response = await fetch(url, {
                    method: "GET",
                    credentials: "include",
                    headers: {
                      "Accept": "application/json, text/plain, */*",
                      "X-XSRF-TOKEN": xsrfToken
                    }
                  });

                  return {
                    ok: response.ok,
                    status: response.status,
                    text: await response.text()
                  };
                }
                """,
                {
                    "apiUrl": api_url,
                    "params": query_params,
                    "xsrfToken": xsrf_token,
                },
            )
        finally:
            if context is not None:
                context.close()
            elif browser is not None:
                browser.close()

    if not response_payload["ok"]:
        raise RuntimeError(
            f"Playwright fetch failed with HTTP {response_payload['status']}: "
            f"{response_payload['text'][:180]}"
        )

    try:
        return json.loads(response_payload["text"])
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Playwright fetch returned non-JSON content. "
            f"Response starts with: {response_payload['text'][:180]}"
        ) from exc


def fetch_remote_page(query_params: dict[str, str]) -> dict:
    fetch_mode = os.getenv("TF2EASY_FETCH_MODE", "playwright").strip().lower()

    if fetch_mode == "http":
        return fetch_remote_page_http(query_params)
    if fetch_mode == "playwright":
        return fetch_remote_page_playwright(query_params)
    if fetch_mode == "auto":
        try:
            return fetch_remote_page_playwright(query_params)
        except Exception:
            return fetch_remote_page_http(query_params)

    raise RuntimeError(f"Unsupported TF2EASY_FETCH_MODE `{fetch_mode}`")


def fetch_remote_leaderboard(query_params: dict[str, str], fetch_all_pages: bool) -> dict:
    if not fetch_all_pages:
        return fetch_remote_page(query_params)

    aggregated_data = []
    current_page = int(query_params.get("page", "1"))
    max_pages = int(os.getenv("TF2EASY_MAX_PAGES", "25"))

    while current_page <= max_pages:
        page_params = dict(query_params)
        page_params["page"] = str(current_page)
        payload = fetch_remote_page(page_params)

        page_data = payload.get("data") or []
        if not page_data:
            break

        aggregated_data.extend(page_data)

        pagination = payload.get("pagination") or {}
        per_page = int(pagination.get("per_page", len(page_data) or 1))
        if len(page_data) < per_page:
            break

        current_page += 1

    return {
        "success": True,
        "data": aggregated_data,
        "pagination": {
            "current_page": 1,
            "per_page": len(aggregated_data),
            "pages_fetched": current_page,
        },
    }


def get_cache_key(query_params: dict[str, str], fetch_all_pages: bool) -> str:
    ordered_params = "&".join(f"{key}={query_params[key]}" for key in sorted(query_params))
    return f"{ordered_params}|all_pages={int(fetch_all_pages)}"


def get_cached_payload(cache_key: str) -> dict | None:
    ttl_seconds = int(os.getenv("TF2EASY_CACHE_SECONDS", "90"))
    if ttl_seconds <= 0:
        return None

    cached = CACHE.get(cache_key)
    if not cached:
        return None

    if time.time() - cached["created_at"] > ttl_seconds:
        CACHE.pop(cache_key, None)
        return None

    return cached["payload"]


def set_cached_payload(cache_key: str, payload: dict) -> None:
    CACHE[cache_key] = {
        "created_at": time.time(),
        "payload": payload,
    }


class AppHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/leaderboard":
            self.handle_leaderboard_api(parsed.query)
            return

        if parsed.path == "/api/health":
            self.respond_json({"ok": True, "service": "StefanlogLB backend"}, HTTPStatus.OK)
            return

        if parsed.path == "/":
            self.path = "/index.html"

        super().do_GET()

    def handle_leaderboard_api(self, query: str) -> None:
        params = parse_qs(query)
        range_value = params.get("range", ["0"])[0]
        query_params = {
            "page": params.get("page", ["1"])[0],
            "status": params.get("status", [""])[0],
            "sortField": params.get("sortField", ["wagered"])[0],
            "sortOrder": params.get("sortOrder", ["desc"])[0],
            "range": range_value,
        }
        fetch_all_pages = "page" not in params
        cache_key = get_cache_key(query_params, fetch_all_pages)
        cached = get_cached_payload(cache_key)

        if cached is not None:
            self.respond_json(cached, HTTPStatus.OK)
            return

        try:
            payload = fetch_remote_leaderboard(query_params, fetch_all_pages=fetch_all_pages)
            set_cached_payload(cache_key, payload)
            self.respond_json(payload, HTTPStatus.OK)
        except RuntimeError as exc:
            self.respond_json(
                {
                    "success": False,
                    "error": str(exc),
                    "fallback": read_local_leaderboard(range_value),
                },
                HTTPStatus.SERVICE_UNAVAILABLE,
            )
        except HTTPError as exc:
            self.respond_json(
                {
                    "success": False,
                    "error": f"TF2Easy returned HTTP {exc.code}",
                    "details": exc.reason,
                    "fallback": read_local_leaderboard(range_value),
                },
                HTTPStatus.BAD_GATEWAY,
            )
        except URLError as exc:
            self.respond_json(
                {
                    "success": False,
                    "error": "Could not reach TF2Easy",
                    "details": str(exc.reason),
                    "fallback": read_local_leaderboard(range_value),
                },
                HTTPStatus.BAD_GATEWAY,
            )
        except Exception as exc:
            self.respond_json(
                {
                    "success": False,
                    "error": "Live TF2Easy fetch failed",
                    "details": str(exc),
                    "fallback": read_local_leaderboard(range_value),
                },
                HTTPStatus.BAD_GATEWAY,
            )

    def respond_json(self, payload: dict, status: HTTPStatus) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    load_env_file()
    os.chdir(BASE_DIR)

    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"Serving StefanlogLB at http://{host}:{port}")
    print("API proxy available at /api/leaderboard")
    print(f"TF2Easy fetch mode: {os.getenv('TF2EASY_FETCH_MODE', 'playwright')}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
