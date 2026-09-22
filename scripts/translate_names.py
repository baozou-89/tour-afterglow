"""Add Traditional Chinese names to shops.geojson (`name`), keeping the Japanese one as `name_ja`.

Order of precedence:
1. Manual overrides in scripts/name_zh_overrides.json (place_id -> name).
2. Chain shops: brand / place-name glossary applied to the Japanese name (keeps the branch name).
3. Google Place Details with languageCode=zh-TW (cached in data/raw/places_zh/), if it really is Chinese.
Anything still untranslated is listed in data/raw/names_todo.json for manual overrides.
"""
import json
import re
import unicodedata
from pathlib import Path

from common import PUBLIC, RAW, http_json, load_key

KANA = re.compile(r"[぀-ヺー-ヿ]")  # kana, but not the middle dot
HAN = re.compile(r"[一-鿿]")
CACHE = RAW / "places_zh"
CACHE.mkdir(parents=True, exist_ok=True)
OVERRIDES = Path(__file__).with_name("name_zh_overrides.json")
overrides = json.loads(OVERRIDES.read_text(encoding="utf-8")) if OVERRIDES.exists() else {}
FOOD = {"restaurant", "izakaya"}

# longest keys first when applied
GLOSSARY = {
    # drugstores
    "ドラッグストアマツモトキヨシ": "松本清藥妝 ", "ドラッグストア マツモトキヨシ": "松本清藥妝 ", "マツモトキヨシ": "松本清藥妝 ",
    "ココカラファイン薬局": "CocoKara Fine 藥局 ", "ココカラファイン": "CocoKara Fine 藥妝 ",
    "ドラッグイレブン": "Drug Eleven 藥妝 ", "ダイコクドラッグ": "大國藥妝 ", "スギ薬局": "杉藥局 ",
    "ツルハドラッグ": "鶴羽藥妝 ", "サンドラッグ": "SunDrug 藥妝 ", "ドラッグストアコスモス": "Cosmos 藥妝 ",
    # electronics
    "ビックカメラ": "BIC CAMERA ", "ヨドバシカメラ マルチメディア": "友都八喜 Multimedia ", "ヨドバシ": "友都八喜",
    "エディオン": "EDION 電器 ", "ヤマダデンキ": "山田電機 ", "テックランド": "Tecc Land ",
    # lifestyle
    "ドン・キホーテ": "唐吉訶德 ", "ダイソー": "大創 DAISO ", "ハンズ ビー": "HANDS BE ", "ハンズ": "HANDS ",
    "ロフト": "LOFT ", "スリーコインズ": "3COINS ",
    # clothing
    "ユニクロ": "UNIQLO ", "ジーユー": "GU ", "ファッションセンターしまむら": "思夢樂 ", "しまむら": "思夢樂 ",
    "アシックスウォーキング": "ASICS Walking ", "アシックス": "ASICS ", "ミズノ": "美津濃 ",
    "プレミアステージ": "Premier Stage ",
    # otaku
    "アニメイト": "animate ", "メロンブックス": "Melonbooks ", "まんだらけ": "Mandarake ", "らしんばん": "Lashinbang ",
    "ポケモンセンターフクオカ": "寶可夢中心 福岡", "ジャンプショップ": "JUMP SHOP ",
    "ヴィレッジヴァンガード": "Village Vanguard ", "トレカ館": "卡牌館",
    # supermarkets
    "マックスバリュエクスプレス": "MaxValu Express ", "マックスバリュ": "MaxValu ", "業務スーパー": "業務超市 ",
    "(株)西鉄ストア": "", "西鉄ストア": "西鐵 Store ", "レガネットキュート": "Reganet Cute ",
    "レガネットマルシェ": "Reganet Marché ", "レガネット": "Reganet 超市 ", "サニー": "SUNNY 超市 ",
    "マルショク": "Marushoku 超市 ", "ゆめマート": "Yume Mart 超市 ", "トキハインダストリー": "TOKIWA Industry 超市 ",
    "アテオ": "ATEO ", "イオン": "AEON ", "スピナ": "SPINA ", "トライアル": "TRIAL ",
    # THE OUTLETS KITAKYUSHU tenants
    "ジ アウトレット北九州": "THE OUTLETS 北九州", "ジアウトレット北九州": "THE OUTLETS 北九州",
    "ジ・アウトレット北九州": "THE OUTLETS 北九州", "ジ·アウトレット北九州": "THE OUTLETS 北九州",
    "ジ アウトレット 北九州": "THE OUTLETS 北九州", "ファクトリーアウトレット": "Factory Outlet ",
    "ファクトリーストア": "Factory Store ", "ファクトリーハウス": "Factory House ", "アウトレットストア": "Outlet Store ",
    "アウトレット": "Outlet ", "コロンビア": "Columbia ", "オークリーボルト": "Oakley Vault ", "グラニフ": "graniph ",
    "東京ソワール": "東京 SOIR ", "マイケル･コース": "Michael Kors ", "アディダスゴルフ": "adidas Golf ", "アディダス": "adidas ",
    "チャイハネ": "Chaihane ", "モンベル": "mont-bell ", "ムラサキスポーツ": "Murasaki Sports ", "フクスケ": "福助 ",
    "リーバイス": "Levi's ", "アンダーアーマー": "UNDER ARMOUR ", "ビームス": "BEAMS ", "マーキーズ": "Markey's ",
    "トミーヒルフィガー": "Tommy Hilfiger ", "コーチ": "COACH ", "(ニコル)": "", "ニューバランス": "New Balance ",
    "ダイアナ": "DIANA ", "プーマ": "PUMA ", "ロゴスショップ": "LOGOS Shop ", "カルバン・クライン": "Calvin Klein ",
    "アーヴェヴェ": "", "セルレ": "CELLURE 美妝 ", "クラッシュゲート×関家具": "Crash Gate × 關家具 ",
    "ペットパラダイス": "Pet Paradise 寵物用品 ", "SN NISHIKAWA × じぶんまくら": "西川 × 自分枕 ", "じぶんまくら": "自分枕 ",
    "ティファール": "T-fal ", "シルバニアファミリー森のお家": "森林家族 森之家", "ジグソーパズルのお店マスターピース": "拼圖專賣店 Masterpiece",
    "韓美膳": "韓美膳 韓國食品 ", "帽子屋OUTLET": "帽子屋 OUTLET ", "帽子屋": "帽子屋 ",
    "THE OUTLETS KITAKYUSHU": "THE OUTLETS 北九州", "KITAKYUSHU": "北九州", "Kitakyushu": "北九州",
    # places / malls
    "アミュプラザくまもと": "AMU PLAZA 熊本", "アミュプラザ博多": "AMU PLAZA 博多", "アミュプラザ": "AMU PLAZA ",
    "アミュエスト": "AMU EST ", "キャナルシティオーパ": "運河城 OPA ", "キャナルシティ博多": "博多運河城",
    "キャナルシティ": "運河城 ", "ノースビル": "北館", "福岡パルコ": "福岡 PARCO ", "パルコ": "PARCO ",
    "博多マルイ": "博多丸井", "マルイ": "丸井", "ミーナ天神": "mina 天神", "ラシック福岡天神": "LACHIC 福岡天神",
    "博多バスターミナル": "博多巴士總站", "ソラリアプラザ": "Solaria Plaza ", "博多リバレイン": "博多 Riverain ",
    "テラソ": "TERASO ", "ららぽーと福岡": "LaLaport 福岡", "イオンモール八幡東": "AEON MALL 八幡東",
    "サクラマチ": "SAKURA MACHI ", "ワンズテラス": "One's Terrace ", "トキハ別府": "TOKIWA 別府",
    "トキハ": "TOKIWA 百貨 ", "鶴屋": "鶴屋百貨",
    "博多駅筑紫口": "博多站筑紫口", "博多駅前": "博多站前", "博多駅東": "博多站東", "博多駅": "博多車站", "駅前": "站前",
    "JR熊本駅": "JR 熊本站", "熊本駅": "熊本站", "駅": "站",
    "天神西通り": "天神西通", "下通り": "下通", "上通り": "上通", "駕町通り": "駕町通", "流川通り": "流川通",
    "鶴高通り": "鶴高通", "通り": "通", "やまなみ": "山並", "渡辺通": "渡邊通", "薬院": "藥院", "天満": "天滿",
    "号館": "號館", "ビル": "大樓", "ゲイツ": "gate's ", "枝光": "枝光", "水産部門": "水產部", "惣菜": "熟食", "上川端": "上川端",
}
KEYS = sorted(GLOSSARY, key=len, reverse=True)


def glossary(name):
    s = unicodedata.normalize("NFKC", name)
    for k in KEYS:
        s = s.replace(unicodedata.normalize("NFKC", k), GLOSSARY[k])
    return re.sub(r"\s+", " ", s).strip()


def good_zh(s):
    return bool(HAN.search(s)) and not KANA.search(s) and "|" not in s


path = PUBLIC / "shops.geojson"
fc = json.loads(path.read_text(encoding="utf-8"))
key = None
todo = {}
for f in fc["features"]:
    p = f["properties"]
    p.setdefault("name_ja", p["name"])
    c = CACHE / f"{p['id']}.json"
    if not c.exists():
        key = key or load_key()
        r = http_json(f"https://places.googleapis.com/v1/places/{p['id']}?languageCode=zh-TW&regionCode=TW",
                      headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask": "displayName"})
        c.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    google = json.loads(c.read_text(encoding="utf-8")).get("displayName", {}).get("text", "")
    if p["id"] in overrides:
        name = overrides[p["id"]]
    elif p["category"] not in FOOD:
        name = glossary(p["name_ja"])
    elif good_zh(google):
        name = google
    else:
        name = glossary(p["name_ja"])
    if p["area"] == "outlets":  # inside the mall the mall name is noise
        name = re.sub(r"\s*THE OUTLETS 北九州店?$|\s*北九州店?$", "", name).strip() or name
    p["name"] = name
    if KANA.search(name) or (p["category"] in FOOD and p["id"] not in overrides and not good_zh(google)):
        todo[p["id"]] = [p["name_ja"], google]

path.write_text(json.dumps(fc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
(RAW / "names_todo.json").write_text(json.dumps(todo, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(fc['features'])} shops, {len(todo)} need a manual name -> data/raw/names_todo.json")
