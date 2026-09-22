"""Search free-time shopping spots with Google Places API (New) -> site/data/shops.geojson.

Each day has a corridor (de-identified base intersection -> biggest nearby station) plus
mall / area circles. Results outside the corridor buffer are dropped.
Raw API responses are cached in data/raw/places_cache/ (gitignored) to avoid re-billing.
"""
import hashlib
import json
import math
import re
import unicodedata
import urllib.parse
from collections import Counter

from common import RAW, dist_to_polyline, haversine, http_json, load_key, point, write_geojson

pois = json.loads((RAW / "pois_private.json").read_text(encoding="utf-8"))
anchors = json.loads((RAW / "anchors_private.json").read_text(encoding="utf-8"))
CACHE = RAW / "places_cache"
CACHE.mkdir(parents=True, exist_ok=True)
KEY = load_key()


def P(k):
    p = anchors[k] if k.startswith("day") else pois[k]
    return (p["lng"], p["lat"])


# kind "line": buffer (m) around a polyline; kind "circle": radius (m) around a point
AREAS = {
    "fukuoka": {"days": [1, 4], "kind": "line", "buffer": 450,
                "line": [P("day1"), P("tenjin"), P("nakasu"), P("hakata_st")]},
    "kumamoto": {"days": [2], "kind": "line", "buffer": 400,
                 "line": [P("day2"), (130.7088, 32.8022), (130.7043, 32.8008), (130.6985, 32.7975), P("kumamoto_st")]},
    "beppu": {"days": [3], "kind": "line", "buffer": 550,
              "line": [P("day3"), (131.4905, 33.2990), P("beppu_st")]},
    "lalaport": {"days": [4], "kind": "circle", "center": P("lalaport"), "radius": 220},
    "mojiko": {"days": [5], "kind": "circle", "center": P("mojiko_st"), "radius": 450},
    "yahata": {"days": [5], "kind": "circle", "center": (130.8113, 33.8720), "radius": 450},
}

# "search term|alias|alias": a result is kept only if its name contains one of the aliases
BRANDS = {
    "otaku": ["アニメイト|animate", "メロンブックス", "まんだらけ", "らしんばん", "駿河屋", "ポケモンセンター|Pokémon",
              "ジャンプショップ|JUMP SHOP", "ガンダムベース|GUNDAM", "ヴィレッジヴァンガード|Village"],
    "drugstore": ["ダイコクドラッグ|ダイコク", "スギ薬局", "マツモトキヨシ", "ドラッグストアコスモス|コスモス", "サンドラッグ",
                  "ツルハドラッグ|ツルハ", "ドラッグイレブン", "ココカラファイン"],
    "supermarket": ["イオン|AEON|マックスバリュ|MaxValu", "サニー|SUNNY", "ローソンストア100", "業務スーパー", "トライアル|TRIAL",
                    "マルショク", "ゆめマート|ゆめタウン", "西鉄ストア|レガネット", "トキハ"],
    "electronics": ["ビックカメラ|BIC", "ヨドバシカメラ|ヨドバシ", "エディオン|EDION", "ヤマダデンキ|ヤマダ"],
    "lifestyle": ["ドン・キホーテ|ドンキ|キホーテ", "3COINS|スリーコインズ", "ロフト|LOFT", "ダイソー|DAISO", "無印良品|MUJI",
                  "ハンズ|HANDS", "セリア|Seria"],
    "clothing": ["ユニクロ|UNIQLO", "ジーユー|GU", "しまむら", "アシックス|ASICS|オニツカ|Onitsuka", "ミズノ|MIZUNO",
                 "ABC-MART|ABCマート"],
}
GENERIC = {
    "restaurant": (["ラーメン", "もつ鍋", "郷土料理", "焼肉", "寿司"],
                   {"restaurant", "ramen_restaurant", "japanese_restaurant", "sushi_restaurant", "barbecue_restaurant",
                    "yakiniku_restaurant", "food_court"}),
    "izakaya": (["居酒屋"], {"izakaya_restaurant", "bar", "japanese_izakaya_restaurant", "restaurant", "pub"}),
}
# restaurants only where dinner is free (Day1 Fukuoka, Day2 Kumamoto)
AREA_CATS = {
    "fukuoka": ["otaku", "drugstore", "supermarket", "electronics", "lifestyle", "clothing", "restaurant", "izakaya"],
    "kumamoto": ["otaku", "drugstore", "supermarket", "electronics", "lifestyle", "clothing", "restaurant", "izakaya"],
    "beppu": ["otaku", "drugstore", "supermarket", "electronics", "lifestyle", "clothing", "izakaya"],
    "lalaport": ["otaku", "drugstore", "supermarket", "electronics", "lifestyle", "clothing"],
    "mojiko": ["otaku", "drugstore", "supermarket", "lifestyle"],
    "yahata": ["otaku", "drugstore", "supermarket", "electronics", "lifestyle", "clothing"],
}
MIN_FOOD = {"rating": 3.7, "count": 80, "keep": 30}

FIELDS = ",".join(["places.id", "places.displayName", "places.location", "places.rating", "places.userRatingCount",
                   "places.primaryType", "places.types", "places.businessStatus", "nextPageToken"])


def norm(s):
    return unicodedata.normalize("NFKC", s).lower().replace(" ", "").replace("　", "")


# prefixes stripped before brand matching, and names that are never shops
PREFIXES = ["【", "(株)", "株式会社", "ドラッグストア", "ファッションセンター", "タイムズ"]
EXCLUDE = re.compile(r"営業所|オフィス|ATM|銀行|駐車場|取扱売場|サービス|カウンター|ブロック|RealSite|倉庫|本社|支社|事務所|物流|^イオンモール", re.I)
SHOP_TYPES = {"store", "supermarket", "grocery_store", "food_store", "drugstore", "pharmacy", "electronics_store",
              "clothing_store", "shoe_store", "department_store", "home_goods_store", "book_store", "shopping_mall",
              "discount_store", "variety_store", "sporting_goods_store", "hobby_store", "toy_store", "gift_shop",
              "convenience_store", "cosmetics_store", "furniture_store", "market"}
BRAND_INDEX = [(norm(al), cat) for cat, qs in BRANDS.items() for q in qs for al in q.split("|")]


def classify(place):
    """Category of a branded shop, judged by the brand its name starts with (None = not ours)."""
    name = norm(place["displayName"]["text"])
    if EXCLUDE.search(name) or not SHOP_TYPES & set(place.get("types", [])) or place.get("userRatingCount", 0) < 5:
        return None
    for pre in PREFIXES:
        if name.startswith(norm(pre)):
            name = name[len(norm(pre)):]
    for al, cat in BRAND_INDEX:
        if name.startswith(al):
            return cat
    return None


def area_rect(a):
    pts, pad = ([a["center"]], a["radius"]) if a["kind"] == "circle" else (a["line"], a["buffer"])
    lngs, lats = [p[0] for p in pts], [p[1] for p in pts]
    dlat = pad / 110540
    dlng = pad / (111320 * math.cos(math.radians(sum(lats) / len(lats))))
    return {"rectangle": {"low": {"latitude": min(lats) - dlat, "longitude": min(lngs) - dlng},
                          "high": {"latitude": max(lats) + dlat, "longitude": max(lngs) + dlng}}}


def inside(a, p):
    if a["kind"] == "circle":
        return haversine(a["center"], p) <= a["radius"]
    return dist_to_polyline(p, a["line"]) <= a["buffer"]


def search(query, rect, pages=1):
    out, token = [], None
    for _ in range(pages):
        body = {"textQuery": query, "languageCode": "ja", "regionCode": "JP", "pageSize": 20, "locationRestriction": rect}
        if token:
            body["pageToken"] = token
        f = CACHE / (hashlib.sha1(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16] + ".json")
        if f.exists():
            r = json.loads(f.read_text(encoding="utf-8"))
        else:
            r = http_json("https://places.googleapis.com/v1/places:searchText", data=body,
                          headers={"X-Goog-Api-Key": KEY, "X-Goog-FieldMask": FIELDS})
            f.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
        out += r.get("places", [])
        token = r.get("nextPageToken")
        if not token:
            break
    return out


shops = {}


def add(place, cat, area):
    if place.get("businessStatus", "OPERATIONAL") != "OPERATIONAL":
        return
    loc = place["location"]
    p = (loc["longitude"], loc["latitude"])
    if not inside(AREAS[area], p):
        return
    pid, name = place["id"], place["displayName"]["text"]
    s = shops.setdefault(pid, {"coords": p, "props": {
        "id": pid, "name": name, "category": cat, "days": [], "area": area,
        "rating": place.get("rating"), "user_ratings_total": place.get("userRatingCount", 0),
        "gmaps_url": "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(name) + "&query_place_id=" + pid}})
    for d in AREAS[area]["days"]:
        if d not in s["props"]["days"]:
            s["props"]["days"].append(d)


for area, cats in AREA_CATS.items():
    rect = area_rect(AREAS[area])
    for cat in cats:
        if cat in BRANDS:
            for q in BRANDS[cat]:
                for pl in search(q.split("|")[0], rect):
                    c = classify(pl)
                    if c and c in cats:
                        add(pl, c, area)
        else:
            queries, types = GENERIC[cat]
            for q in queries:
                for pl in search(q, rect, pages=2):
                    if types & set(pl.get("types", [])) and (pl.get("rating") or 0) >= MIN_FOOD["rating"] \
                            and pl.get("userRatingCount", 0) >= MIN_FOOD["count"]:
                        add(pl, cat, area)
        print(f"{area:9s} {cat:12s} total={len(shops)}")

# food: keep only the best per area
for cat in ("restaurant", "izakaya"):
    for area in AREAS:
        items = [s for s in shops.values() if s["props"]["category"] == cat and s["props"]["area"] == area]
        items.sort(key=lambda s: s["props"]["rating"] * math.log10(s["props"]["user_ratings_total"] + 10), reverse=True)
        for s in items[MIN_FOOD["keep"]:]:
            del shops[s["props"]["id"]]

feats = []
for s in shops.values():
    s["props"]["days"].sort()
    feats.append(point(*s["coords"], s["props"]))
feats.sort(key=lambda f: (f["properties"]["days"][0], f["properties"]["category"], -(f["properties"]["rating"] or 0)))
write_geojson("shops.geojson", feats)
for k, v in sorted(Counter((f["properties"]["area"], f["properties"]["category"]) for f in feats).items()):
    print(k, v)
