"""Build public itinerary layers from the private POI file.

- Hotels are replaced by the nearest road intersection (no names, no exact position).
- Outputs site/data/pois.geojson and site/data/uncertain.geojson, plus data/raw/anchors_private.json.
"""
import json
from collections import defaultdict
from common import RAW, haversine, overpass, point, write_geojson

pois = json.loads((RAW / "pois_private.json").read_text(encoding="utf-8"))

ROADS = "primary|secondary|tertiary|unclassified|residential|primary_link|secondary_link|trunk"


def nearest_intersection(lng, lat, min_d=40, radius=350):
    q = f'[out:json][timeout:60];way(around:{radius},{lat},{lng})[highway~"^({ROADS})$"];out body;>;out skel qt;'
    r = overpass(q)
    nodes = {e["id"]: (e["lon"], e["lat"]) for e in r["elements"] if e["type"] == "node"}
    ways_at = defaultdict(list)
    for w in (e for e in r["elements"] if e["type"] == "way"):
        tag = w.get("tags", {})
        for n in w["nodes"]:
            ways_at[n].append((w["id"], tag.get("name"), tag.get("highway")))
    best = None
    for nid, ws in ways_at.items():
        if len({w[0] for w in ws}) < 2 or nid not in nodes:
            continue
        names = {w[1] for w in ws if w[1]}
        major = sum(1 for w in ws if w[2] in ("primary", "secondary", "tertiary", "trunk"))
        d = haversine((lng, lat), nodes[nid])
        if d < min_d:
            continue
        # prefer named / major crossings: penalise unnamed ones as if 60 m farther
        score = d - 25 * min(len(names), 2) - 15 * min(major, 2)
        if best is None or score < best[0]:
            best = (score, nodes[nid], d, sorted(names))
    return best


anchors = {}
for day, hid in [(1, "hotel_fukuoka"), (2, "hotel_kumamoto"), (3, "hotel_beppu"), (4, "hotel_fukuoka")]:
    h = pois[hid]
    if hid not in anchors:
        b = nearest_intersection(h["lng"], h["lat"])
        anchors[hid] = {"lng": b[1][0], "lat": b[1][1], "offset_m": round(b[2]), "roads": b[3]}
        print(hid, "->", anchors[hid])
    anchors[f"day{day}"] = anchors[hid]
(RAW / "anchors_private.json").write_text(json.dumps(anchors, ensure_ascii=False, indent=1), encoding="utf-8")

# Public labels (Traditional Chinese). Hotels are never named.
SIGHTS = {
    "fuk_airport": ("福岡機場", [1, 5], "airport"),
    "hakata_st": ("博多車站", [1, 4], "station"),
    "tenjin": ("天神", [1, 4], "station"),
    "nakasu": ("中洲（屋台）", [1, 4], "sight"),
    "kumamoto_castle": ("熊本城", [2], "sight"),
    "sakuranobaba": ("櫻之馬場 城彩苑", [2], "sight"),
    "kumamoto_st": ("熊本車站", [2], "station"),
    "kusasenri": ("阿蘇草千里", [3], "sight"),
    "yunotsubo": ("湯之坪街道", [3], "sight"),
    "floral_village": ("湯布院童話村", [3], "sight"),
    "kinrinko": ("金鱗湖", [3], "sight"),
    "beppu_st": ("別府車站", [3], "station"),
    "dazaifu": ("太宰府天滿宮", [4], "sight"),
    "lalaport": ("LaLaport 福岡・1:1 鋼彈", [4], "mall"),
    "mojiko_st": ("門司港車站", [5], "sight"),
    "old_moji_customs": ("舊門司稅關", [5], "sight"),
    "old_mitsui_club": ("舊門司三井俱樂部", [5], "sight"),
    "kaikyo_plaza": ("海峽廣場", [5], "sight"),
    "outlets_kitakyushu": ("THE OUTLETS 北九州", [5], "mall"),
    "aeon_yahatahigashi": ("AEON MALL 八幡東", [5], "mall"),
}
features = []
for pid, (label, days, kind) in SIGHTS.items():
    p = pois[pid]
    features.append(point(p["lng"], p["lat"], {"id": pid, "name": label, "kind": kind, "days": days,
                                                  "gmaps_url": f"https://www.google.com/maps/search/?api=1&query={p['lat']:.6f},{p['lng']:.6f}&query_place_id={p['place_id']}"}))
for day in (1, 2, 3, 4):
    a = anchors[f"day{day}"]
    features.append(point(a["lng"], a["lat"], {"id": f"base{day}", "name": f"Day{day} 據點", "kind": "base", "days": [day]}))
write_geojson("pois.geojson", features)

# Locations that are not confirmed: shown as dashed circles only.
UNCERTAIN = [
    ("wagashi", "和果子手作體驗", [2], 32.80, 130.72, 6000, "地點未公布，推測在熊本市區周邊"),
    ("dutyfree", "免稅店", [4], 33.57, 130.47, 6000, "地點未公布，推測在太宰府往 LaLaport 途中"),
    ("yakiniku", "和牛燒肉吃到飽", [4], 33.58, 130.41, 3000, "地點未公布，推測在福岡市區"),
]
write_geojson("uncertain.geojson", [point(lng, lat, {"id": i, "name": n, "days": d, "radius_m": r, "note": note})
                                     for i, n, d, lat, lng, r, note in UNCERTAIN])
