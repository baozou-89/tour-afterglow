"""Bus / tram lines linking each day's base to its shopping hub -> site/data/transit.geojson.

Candidate lines are OSM route relations (Overpass) that pass within walking distance of BOTH
the base intersection and the target. Geometry is clipped to the box around the two ends.
Frequency is not in OSM: `headway` stays null unless filled in by hand from the operator timetable.
"""
import json
import math
from common import RAW, haversine, overpass, write_geojson

pois = json.loads((RAW / "pois_private.json").read_text(encoding="utf-8"))
anchors = json.loads((RAW / "anchors_private.json").read_text(encoding="utf-8"))

# (days, from anchor, to poi, label, walk radius at base, radius at target, max lines)
LINKS = [
    ([1, 4], "day1", "hakata_st", "博多車站", 250, 350, 3),
    ([1, 4], "day1", "nakasu", "中洲・運河城", 250, 400, 2),
    ([2], "day2", "kumamoto_st", "熊本車站", 350, 350, 3),
    ([3], "day3", "beppu_st", "別府車站", 350, 350, 3),
]
# frequent services from operator timetables (evening, minutes); keyed by (operator-ish, ref)
HEADWAY = {}


def ll(k):
    p = anchors[k] if k.startswith("day") else pois[k]
    return p["lng"], p["lat"]


def relations_near(lng, lat, r):
    """Route relations that have a stop/platform within r metres (cheap: stops first, then parents)."""
    q = (f'[out:json][timeout:90];(node(around:{r},{lat},{lng})[highway=bus_stop];'
         f'node(around:{r},{lat},{lng})[railway=tram_stop];'
         f'node(around:{r},{lat},{lng})[public_transport~"^(platform|stop_position)$"];);'
         'rel(bn)[type=route][route~"^(bus|tram)$"];out tags;')
    return {e["id"]: e.get("tags", {}) for e in overpass(q)["elements"]}


def clip(ways, a, b, pad=500):
    lat0 = (a[1] + b[1]) / 2
    dlat, dlng = pad / 110540, pad / (111320 * math.cos(math.radians(lat0)))
    x0, x1 = min(a[0], b[0]) - dlng, max(a[0], b[0]) + dlng
    y0, y1 = min(a[1], b[1]) - dlat, max(a[1], b[1]) + dlat
    out = []
    for w in ways:
        seg = []
        for x, y in w:
            if x0 <= x <= x1 and y0 <= y <= y1:
                seg.append([round(x, 5), round(y, 5)])
            elif len(seg) > 1:
                out.append(seg); seg = []
            else:
                seg = []
        if len(seg) > 1:
            out.append(seg)
    return out


def length(lines):
    return sum(haversine(l[i], l[i + 1]) for l in lines for i in range(len(l) - 1))


features = []
for days, a, b, label, ra, rb, n in LINKS:
    A, B = ll(a), ll(b)
    both = relations_near(*A, ra)
    near_b = relations_near(*B, rb)
    ids = [i for i in both if i in near_b]
    print(f"Day{days} -> {label}: {len(ids)} candidate relations")
    if not ids:
        continue
    q = "[out:json][timeout:120];(" + "".join(f"relation({i});" for i in ids) + ");out geom;"
    cands = []
    for rel in overpass(q)["elements"]:
        tags = rel.get("tags", {})
        ways = [[(g["lon"], g["lat"]) for g in m["geometry"]] for m in rel.get("members", [])
                if m["type"] == "way" and m.get("geometry") and m.get("role", "") in ("", "forward", "backward")]
        lines = clip(ways, A, B)
        if not lines:
            continue
        cands.append({"tags": tags, "lines": lines, "len": length(lines)})
    # one entry per line ref (drop the reverse direction), trams first, then most direct
    cands.sort(key=lambda c: (c["tags"].get("route") != "tram", c["len"]))
    seen = set()
    for c in cands:
        t = c["tags"]
        ref = t.get("ref") or t.get("name", "")
        key = (t.get("operator", ""), ref)
        if key in seen:
            continue
        seen.add(key)
        features.append({"type": "Feature", "geometry": {"type": "MultiLineString", "coordinates": c["lines"]},
                         "properties": {"days": days, "to": label, "mode": t.get("route"), "ref": ref,
                                        "name": t.get("name:ja") or t.get("name", ""), "operator": t.get("operator", ""),
                                        "headway_min": HEADWAY.get(key)}})
        print("   ", t.get("route"), ref, t.get("operator"), t.get("name"))
        if len([f for f in features if f["properties"]["to"] == label]) >= n:
            break
write_geojson("transit.geojson", features)
