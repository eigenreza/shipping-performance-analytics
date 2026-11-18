"""Small HTTP helper with retries and a neutral client name."""

from __future__ import annotations

import time
from pathlib import Path

import requests

USER_AGENT = "shipping-performance-analytics/1.0 (open data research)"


def session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


def get(url: str, *, params=None, timeout=120, retries=4, sess: requests.Session | None = None, **kw):
    s = sess or session()
    for attempt in range(retries):
        try:
            r = s.get(url, params=params, timeout=timeout, **kw)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"HTTP {r.status_code}")
            r.raise_for_status()
            return r
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError):
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt * 2)
    raise RuntimeError("unreachable")


def download(url: str, dest: Path, **kw) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = get(url, **kw)
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(r.content)
    tmp.replace(dest)
    return dest.stat().st_size
