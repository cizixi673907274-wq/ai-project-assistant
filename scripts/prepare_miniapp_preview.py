#!/usr/bin/env python3
"""Prepare the WeChat miniapp dist bundle for LAN device preview."""

from __future__ import annotations

import argparse
import json
import re
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST_COMMON = ROOT / "apps" / "miniapp" / "dist" / "common.js"
DEFAULT_MOBILE = "13800005678"
DEFAULT_CODE = "123456"
API_PATTERN = re.compile(r"http://(?:localhost|127\.0\.0\.1|(?:\d{1,3}\.){3}\d{1,3}):8000/api/v1")


def run(command: list[str]) -> str:
    return subprocess.check_output(command, text=True, stderr=subprocess.DEVNULL).strip()


def detect_lan_ip() -> str:
    for interface in ("en0", "en1"):
        try:
            value = run(["ipconfig", "getifaddr", interface])
            if value:
                return value
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    # Cross-platform fallback. It does not send packets; it only asks the OS
    # which local address would be used for this route.
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]


def post_json(url: str, payload: dict[str, str], timeout: float = 5) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def verify_login(api_base: str, mobile: str, code: str) -> None:
    body = post_json(f"{api_base}/auth/mobile/login", {"mobile": mobile, "code": code})
    if not body.get("success") or not body.get("data", {}).get("access_token"):
        raise RuntimeError(f"login check failed: {body}")


def patch_dist(api_base: str) -> bool:
    if not DIST_COMMON.exists():
        raise FileNotFoundError(f"miniapp dist file not found: {DIST_COMMON}")
    source = DIST_COMMON.read_text(encoding="utf-8")
    patched, count = API_PATTERN.subn(api_base, source)
    if count == 0 and api_base not in source:
        raise RuntimeError("could not find an API base URL in apps/miniapp/dist/common.js")
    if patched != source:
        DIST_COMMON.write_text(patched, encoding="utf-8")
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", help="LAN IP or hostname for the API server")
    parser.add_argument("--port", default="8000", help="API server port")
    parser.add_argument("--mobile", default=DEFAULT_MOBILE, help="test mobile number")
    parser.add_argument("--code", default=DEFAULT_CODE, help="test verification code")
    parser.add_argument("--skip-login-check", action="store_true", help="only patch the miniapp bundle")
    args = parser.parse_args()

    host = args.host or detect_lan_ip()
    api_base = f"http://{host}:{args.port}/api/v1"

    if not args.skip_login_check:
        verify_login(api_base, args.mobile, args.code)

    changed = patch_dist(api_base)
    print(json.dumps({"api_base": api_base, "dist_common": str(DIST_COMMON), "changed": changed}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, urllib.error.URLError) as exc:
        print(f"prepare miniapp preview failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
