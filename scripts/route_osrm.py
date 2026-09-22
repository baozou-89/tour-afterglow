"""Draft coach routes per day with the public OSRM demo server -> site/data/routes.geojson.

Start/end points use the de-identified intersection anchors, never the hotels themselves.
"""
import json
import time
from common import RAW, http_json, write_geojson

pois = json.loads((RAW / "pois_private.json").read_text(encoding="utf-8"))
anchors = json.loads((RAW / "anchors_private.json").read_text(encoding="utf-8"))

LABEL = {"fuk_airport": "福岡機場", "kumamoto_castle": "熊本城", "sakuranobaba": "櫻之馬場", "kusasenri": "草千里",
         "yunotsubo": "湯布院", "dazaifu": "太宰府", "lalaport": "LaLaport", "mojiko_st": "門司港",
         "outlets_kitakyushu": "THE OUTLETS", "aeon_yahatahigashi": "AEON MALL"}
DAYS = {
    1: ["fuk_airport", "day1"],
    2: ["day1", "kumamoto_castle", "sakuranobaba", "day2"],
    3: ["day2", "kusasenri", "yunotsubo", "day3"],
    4: ["day3", "dazaifu", "lalaport", "day4"],
    5: ["day4", "mojiko_st", "outlets_kitakyushu", "aeon_yahatahigashi", "fuk_airport"],
}


def coord(k):
    p = anchors[k] if k.startswith("day") else pois[k]
    return p["lng"], p["lat"]


def label(k):
    return f"Day{k[3:]} 據點" if k.startswith("day") else LABEL[k]


features = []
for day, stops in DAYS.items():
    for seq, (a, b) in enumerate(zip(stops, stops[1:]), 1):
        (x1, y1), (x2, y2) = coord(a), coord(b)
        url = (f"https://router.project-osrm.org/route/v1/driving/{x1:.6f},{y1:.6f};{x2:.6f},{y2:.6f}"
               "?overview=simplified&geometries=geojson")
        r = http_json(url)
        route = r["routes"][0]
        geom = route["geometry"]
        geom["coordinates"] = [[round(x, 5), round(y, 5)] for x, y in geom["coordinates"]]
        features.append({"type": "Feature", "geometry": geom, "properties": {
            "day": day, "seq": seq, "from": label(a), "to": label(b),
            "distance_km": round(route["distance"] / 1000, 1), "duration_min": round(route["duration"] / 60)}})
        print(f"Day{day} {seq}: {label(a)} -> {label(b)} {route['distance']/1000:.1f} km")
        time.sleep(1)
write_geojson("routes.geojson", features)
