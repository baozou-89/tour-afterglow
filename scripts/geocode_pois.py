"""Geocode itinerary places with Places API (New) Text Search -> data/raw/pois_private.json (gitignored)."""
import json
from common import RAW, http_json, load_key

# [id, query, kind (hotel|sight|station|mall|airport)] -- kept private because it names the hotels
QUERIES = json.loads((RAW / "geocode_queries.json").read_text(encoding="utf-8"))

key = load_key()
out = {}
for pid, q, kind in QUERIES:
    r = http_json("https://places.googleapis.com/v1/places:searchText",
                  data={"textQuery": q, "languageCode": "ja", "regionCode": "JP", "maxResultCount": 1},
                  headers={"X-Goog-Api-Key": key,
                           "X-Goog-FieldMask": "places.id,places.displayName,places.location,places.formattedAddress"})
    p = (r.get("places") or [None])[0]
    if not p:
        print("NOT FOUND", pid, q); continue
    out[pid] = {"kind": kind, "query": q, "name": p["displayName"]["text"], "place_id": p["id"],
                "address": p.get("formattedAddress"), "lng": p["location"]["longitude"], "lat": p["location"]["latitude"]}
    print(pid, "->", out[pid]["name"], out[pid]["lat"], out[pid]["lng"])

RAW.mkdir(parents=True, exist_ok=True)
(RAW / "pois_private.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
