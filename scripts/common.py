"""Shared helpers for the data pipeline (stdlib only)."""
import json
import math
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PUBLIC = ROOT / "site" / "data"
try:
    import certifi
    SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:  # CI runners have a sane system store
    SSL_CTX = ssl.create_default_context()
UA = "tour-afterglow-data-builder/1.0 (personal trip map)"


def load_key():
    import os
    if os.environ.get("GOOGLE_PLACES_API_KEY"):
        return os.environ["GOOGLE_PLACES_API_KEY"]
    for line in (ROOT / "key.env").read_text(encoding="utf-8").splitlines():
        if line.startswith("GOOGLE_PLACES_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("GOOGLE_PLACES_API_KEY not found")


def http_json(url, data=None, headers=None, retries=3):
    body = None
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    if data is not None:
        if isinstance(data, (dict, list)):
            body = json.dumps(data).encode()
            h.setdefault("Content-Type", "application/json")
        else:
            body = data.encode() if isinstance(data, str) else data
    for i in range(retries):
        try:
            req = urllib.request.Request(url, data=body, headers=h)
            with urllib.request.urlopen(req, timeout=180, context=SSL_CTX) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            if i == retries - 1:
                raise
            print("  retry", i + 1, e)
            time.sleep(3 * (i + 1))


OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]


def overpass(query):
    last = None
    for url in OVERPASS_MIRRORS:
        try:
            return http_json(url, data="data=" + urllib.parse.quote(query),
                             headers={"Content-Type": "application/x-www-form-urlencoded"}, retries=2)
        except Exception as e:  # noqa: BLE001
            print("  overpass mirror failed:", url, str(e)[:80])
            last = e
    raise last


def haversine(a, b):
    """Distance in metres between (lng, lat) pairs."""
    lng1, lat1, lng2, lat2 = map(math.radians, (*a, *b))
    d = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(d))


def dist_to_segment(p, a, b):
    """Approx. metres from point p to segment a-b (local equirectangular)."""
    k = math.cos(math.radians(p[1]))
    def xy(q):
        return (q[0] * 111320 * k, q[1] * 110540)
    px, py = xy(p); ax, ay = xy(a); bx, by = xy(b)
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def dist_to_polyline(p, line):
    return min(dist_to_segment(p, line[i], line[i + 1]) for i in range(len(line) - 1)) if len(line) > 1 else haversine(p, line[0])


def write_geojson(name, features):
    PUBLIC.mkdir(parents=True, exist_ok=True)
    path = PUBLIC / name
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)} ({len(features)} features)")


def point(lng, lat, props):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(lng, 6), round(lat, 6)]}, "properties": props}
