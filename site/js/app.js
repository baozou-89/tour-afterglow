(() => {
  "use strict";

  const CATS = {
    otaku: { label: "宅店", color: "#7A4FB5" },
    drugstore: { label: "藥妝", color: "#C23B74" },
    restaurant: { label: "餐廳", color: "#B4491A" },
    izakaya: { label: "居酒屋", color: "#8E2F24" },
    supermarket: { label: "超市", color: "#3B7F4A" },
    electronics: { label: "電器", color: "#2C62A8" },
    lifestyle: { label: "生活雜貨", color: "#B8860B" },
    clothing: { label: "服飾", color: "#1F6A72" },
  };
  const GSI = '<a href="https://maps.gsi.go.jp/development/ichiran.html" target="_blank" rel="noopener">出典：国土地理院</a>';
  const OSM = '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors</a>';
  const BASEMAPS = {
    osm: { attr: OSM },
    pale: { attr: GSI + "（淡色地図）" },
    photo: { attr: GSI + "（写真）" },
  };
  const EXTRA_ATTR = "路線 © OSRM／" + OSM + "・商家資料 © Google";

  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch { /* private mode */ } },
  };
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // ---------- which day to open ----------
  function initialDay() {
    const q = parseInt(new URLSearchParams(location.search).get("day"), 10);
    if (TRIP.days[q]) return q;
    const n = Math.floor((Date.now() - Date.parse(TRIP.start)) / 86400000) + 1;
    if (TRIP.days[n]) return n; // during the trip: follow the calendar
    const saved = parseInt(store.get("ta.day"), 10);
    return TRIP.days[saved] ? saved : 1;
  }

  const state = {
    day: initialDay(),
    basemap: BASEMAPS[store.get("ta.basemap")] ? store.get("ta.basemap") : "osm",
    cats: new Set(Object.keys(CATS)),
    routes: true,
    transit: true,
    pois: true,
    uncertain: true,
  };
  let data = {};
  let markers = [];

  // ---------- map ----------
  const raster = (tiles, maxzoom, attribution) => ({ type: "raster", tiles: [tiles], tileSize: 256, maxzoom, attribution });
  const map = new maplibregl.Map({
    container: "map",
    attributionControl: false,
    localIdeographFontFamily: "'Noto Sans TC', 'PingFang TC', 'Microsoft JhengHei', sans-serif",
    bounds: TRIP.days[state.day].bounds,
    fitBoundsOptions: { padding: fitPadding() },
    style: {
      version: 8,
      glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
      sources: {
        osm: raster("https://tile.openstreetmap.org/{z}/{x}/{y}.png", 19, ""),
        pale: raster("https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png", 18, ""),
        photo: raster("https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/{z}/{x}/{y}.jpg", 18, ""),
      },
      layers: Object.keys(BASEMAPS).map((id) => ({
        id: "bm-" + id, type: "raster", source: id,
        layout: { visibility: id === state.basemap ? "visible" : "none" },
      })),
    },
  });
  // style.load fires once; isStyleLoaded() is false while basemap tiles are still loading
  let styleReady = false;
  map.once("style.load", () => { styleReady = true; });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  map.addControl(new maplibregl.GeolocateControl({ positionOptions: { enableHighAccuracy: true }, trackUserLocation: true }), "top-right");

  function fitPadding() {
    const wide = window.innerWidth >= 900;
    const sheet = document.getElementById("sheet");
    const bottom = sheet ? sheet.offsetHeight + 16 : 240;
    return wide ? { top: 40, bottom: 40, left: 460, right: 60 } : { top: 140, bottom, left: 20, right: 20 };
  }

  // ---------- UI: day tabs ----------
  const $ = (id) => document.getElementById(id);
  const daysNav = $("days");
  Object.keys(TRIP.days).forEach((d) => {
    const b = document.createElement("button");
    b.type = "button";
    b.role = "tab";
    b.textContent = "Day" + d;
    b.dataset.day = d;
    b.addEventListener("click", () => { store.set("ta.day", d); setDay(+d, true); });
    daysNav.appendChild(b);
  });

  document.querySelectorAll("[data-basemap]").forEach((b) =>
    b.addEventListener("click", () => setBasemap(b.dataset.basemap)));

  $("grip").addEventListener("click", () => {
    const c = $("sheet").classList.toggle("collapsed");
    $("grip").setAttribute("aria-expanded", String(!c));
  });

  function setBasemap(id) {
    state.basemap = id;
    store.set("ta.basemap", id);
    Object.keys(BASEMAPS).forEach((k) => map.setLayoutProperty("bm-" + k, "visibility", k === id ? "visible" : "none"));
    document.querySelectorAll("[data-basemap]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.basemap === id)));
    // shop dots need a darker halo on aerial photos
    if (map.getLayer("shops")) map.setPaintProperty("shops", "circle-stroke-color", id === "photo" ? "#2A2521" : "#FFFFFF");
    renderAttrib();
  }

  function renderAttrib() {
    $("attrib").innerHTML = "底圖 " + BASEMAPS[state.basemap].attr + " ・" + EXTRA_ATTR;
  }

  function setDay(d, animate) {
    state.day = d;
    const cfg = TRIP.days[d];
    $("dayTitle").textContent = cfg.title;
    $("dayArea").textContent = cfg.area;
    daysNav.querySelectorAll("button").forEach((b) => b.setAttribute("aria-selected", String(+b.dataset.day === d)));
    map.fitBounds(cfg.bounds, { padding: fitPadding(), duration: animate ? 900 : 0 });
    if (data.shops) { applyFilters(); renderMarkers(); renderChips(); renderList(); }
  }

  // ---------- filters ----------
  const onDay = () => ["in", state.day, ["get", "days"]];
  function applyFilters() {
    const shopFilter = ["all", onDay(), ["in", ["get", "category"], ["literal", [...state.cats]]]];
    ["shops", "shop-labels"].forEach((l) => map.setFilter(l, shopFilter));
    map.setFilter("routes", ["==", ["get", "day"], state.day]);
    map.setFilter("routes-casing", ["==", ["get", "day"], state.day]);
    map.setFilter("transit", onDay());
    map.setLayoutProperty("routes", "visibility", state.routes ? "visible" : "none");
    map.setLayoutProperty("routes-casing", "visibility", state.routes ? "visible" : "none");
    map.setLayoutProperty("transit", "visibility", state.transit ? "visible" : "none");
    ["uncertain-fill", "uncertain-line"].forEach((l) => {
      map.setFilter(l, onDay());
      map.setLayoutProperty(l, "visibility", state.uncertain ? "visible" : "none");
    });
  }

  const dayShops = () => data.shops.features.filter((f) => f.properties.days.includes(state.day));

  function renderChips() {
    const counts = {};
    dayShops().forEach((f) => { counts[f.properties.category] = (counts[f.properties.category] || 0) + 1; });
    const wrap = $("chips");
    wrap.textContent = "";
    Object.entries(CATS).forEach(([k, c]) => {
      const n = counts[k] || 0;
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip";
      b.style.setProperty("--c", c.color);
      b.setAttribute("aria-pressed", String(n > 0 && state.cats.has(k)));
      b.disabled = n === 0;
      b.innerHTML = esc(c.label) + ' <span class="n">' + n + "</span>";
      b.addEventListener("click", () => {
        state.cats.has(k) ? state.cats.delete(k) : state.cats.add(k);
        applyFilters(); renderChips(); renderList();
      });
      wrap.appendChild(b);
    });

    const lw = $("layerChips");
    lw.textContent = "";
    const has = (fc) => fc.features.some((f) => f.properties.days.includes(state.day));
    [["pois", "景點・車站", "#6B5847", true], ["routes", "行車路線", "#B4491A", true],
      ["transit", "公車・市電", "#1F6A72", has(data.transit)], ["uncertain", "位置未定", "#B4491A", has(data.uncertain)],
    ].forEach(([k, label, color, ok]) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip";
      b.style.setProperty("--c", color);
      b.disabled = !ok;
      b.setAttribute("aria-pressed", String(state[k] && ok));
      b.textContent = label;
      b.addEventListener("click", () => { state[k] = !state[k]; applyFilters(); renderMarkers(); renderChips(); });
      lw.appendChild(b);
    });
  }

  // rating weighted by review count, so a 5.0 with 3 reviews does not top the list
  const score = (p) => (p.rating || 0) * Math.log10((p.user_ratings_total || 0) + 10);

  function renderList() {
    const ol = $("shopList");
    ol.textContent = "";
    dayShops()
      .filter((f) => state.cats.has(f.properties.category))
      .sort((a, b) => score(b.properties) - score(a.properties))
      .forEach((f) => {
        const p = f.properties;
        const li = document.createElement("li");
        const b = document.createElement("button");
        b.type = "button";
        b.style.setProperty("--c", CATS[p.category].color);
        b.innerHTML = '<span class="dot"></span><span class="nm">' + esc(p.name) + '</span><span class="rt">' +
          (p.rating ? "★ " + p.rating.toFixed(1) : "—") + "</span>";
        b.addEventListener("click", () => {
          $("sheet").classList.add("collapsed");
          $("grip").setAttribute("aria-expanded", "false");
          map.easeTo({ center: f.geometry.coordinates, zoom: Math.max(map.getZoom(), 16), offset: [0, 70] });
          shopPopup(f, "bottom");
        });
        li.appendChild(b);
        ol.appendChild(li);
      });
  }

  // ---------- markers (HTML, so CJK labels need no glyph server) ----------
  function renderMarkers() {
    markers.forEach((m) => m.remove());
    markers = [];
    data.pois.features.filter((f) => f.properties.days.includes(state.day) && (state.pois || f.properties.kind === "base")).forEach((f) => {
      const p = f.properties;
      const el = document.createElement("div");
      if (p.kind === "base") {
        el.className = "mk-base";
        el.textContent = "D" + state.day;
        el.title = p.name;
      } else {
        el.className = "mk-poi " + p.kind;
        el.innerHTML = "<i></i><b>" + esc(p.name) + "</b>";
      }
      const m = new maplibregl.Marker({ element: el, anchor: p.kind === "base" ? "center" : "left", offset: p.kind === "base" ? [0, 0] : [-8, 0] })
        .setLngLat(f.geometry.coordinates).addTo(map);
      if (p.kind !== "base") {
        el.addEventListener("click", (e) => { e.stopPropagation(); poiPopup(f); });
      }
      markers.push(m);
    });
    data.uncertain.features.filter((f) => state.uncertain && f.properties.days.includes(state.day)).forEach((f) => {
      const el = document.createElement("div");
      el.className = "mk-unknown";
      el.textContent = "?";
      el.title = f.properties.name;
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        popup(f.geometry.coordinates, "#B4491A", "位置未定", f.properties.name, '<div class="pp-note">' + esc(f.properties.note) + "</div>");
      });
      markers.push(new maplibregl.Marker({ element: el }).setLngLat(f.geometry.coordinates).addTo(map));
    });
  }

  // ---------- popups ----------
  let openPopup;
  function popup(lngLat, color, tag, name, body, anchor) {
    if (openPopup) openPopup.remove();
    const html = '<div class="pp-bar" style="--c:' + color + '"></div><div class="pp" style="--c:' + color + '">' +
      '<span class="pp-tag">' + esc(tag) + '</span><div class="pp-name">' + esc(name) + "</div>" + body + "</div>";
    openPopup = new maplibregl.Popup({ maxWidth: "300px", offset: 12, focusAfterOpen: false, anchor }).setLngLat(lngLat).setHTML(html).addTo(map);
  }
  const goBtn = (url) => '<a class="pp-go" href="' + esc(url) + '" target="_blank" rel="noopener">' +
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/></svg>在 Google 地圖開啟</a>';

  function shopPopup(f, anchor) {
    const p = f.properties;
    const c = CATS[p.category];
    const rating = p.rating
      ? '<div class="pp-rating">★ ' + p.rating.toFixed(1) + " <small>(" + (p.user_ratings_total || 0).toLocaleString() + " 則評論)</small></div>"
      : '<div class="pp-note">尚無 Google 評分</div>';
    const ja = p.name_ja && p.name_ja !== p.name ? '<div class="pp-ja" lang="ja">' + esc(p.name_ja) + "</div>" : "";
    popup(f.geometry.coordinates, c.color, c.label, p.name, ja + rating + goBtn(p.gmaps_url), anchor);
  }
  function poiPopup(f) {
    const p = f.properties;
    const tag = { sight: "景點", station: "車站", mall: "購物中心", airport: "機場" }[p.kind] || "地點";
    popup(f.geometry.coordinates, "#B4491A", tag, p.name, p.gmaps_url ? goBtn(p.gmaps_url) : "");
  }

  // circle polygons for "location unknown" areas
  function circle(center, r) {
    const [lng, lat] = center;
    const pts = [];
    for (let i = 0; i <= 64; i++) {
      const a = (i / 64) * 2 * Math.PI;
      pts.push([lng + (r * Math.cos(a)) / (111320 * Math.cos((lat * Math.PI) / 180)), lat + (r * Math.sin(a)) / 110540]);
    }
    return pts;
  }

  // ---------- load data ----------
  const load = (n) => fetch("data/" + n + ".geojson").then((r) => r.json());
  Promise.all(["pois", "uncertain", "routes", "shops", "transit"].map(load)).then(([pois, uncertain, routes, shops, transit]) => {
    data = { pois, uncertain, routes, shops, transit };
    const ready = () => {
      map.addSource("routes", { type: "geojson", data: routes });
      map.addSource("transit", { type: "geojson", data: transit });
      map.addSource("shops", { type: "geojson", data: shops });
      map.addSource("uncertain", {
        type: "geojson",
        data: { type: "FeatureCollection", features: uncertain.features.map((f) => ({
          type: "Feature", properties: f.properties,
          geometry: { type: "Polygon", coordinates: [circle(f.geometry.coordinates, f.properties.radius_m)] },
        })) },
      });
      map.addLayer({ id: "uncertain-fill", type: "fill", source: "uncertain", paint: { "fill-color": "#B4491A", "fill-opacity": 0.08 } });
      map.addLayer({ id: "uncertain-line", type: "line", source: "uncertain", paint: { "line-color": "#B4491A", "line-width": 2, "line-dasharray": [3, 2] } });
      map.addLayer({ id: "routes-casing", type: "line", source: "routes", layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#FFFFFF", "line-width": 8, "line-opacity": 0.8 } });
      map.addLayer({ id: "routes", type: "line", source: "routes", layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#B4491A", "line-width": 4.5 } });
      map.addLayer({ id: "transit", type: "line", source: "transit", layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": ["match", ["get", "mode"], "tram", "#2C62A8", "#1F6A72"], "line-width": 4, "line-dasharray": [0.6, 1.8] } });
      const catColor = ["match", ["get", "category"]];
      Object.entries(CATS).forEach(([k, c]) => catColor.push(k, c.color));
      catColor.push("#888");
      map.addLayer({ id: "shops", type: "circle", source: "shops", paint: {
        "circle-color": catColor,
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 12, 4, 15, 7, 18, 10],
        "circle-stroke-width": 2, "circle-stroke-color": "#FFFFFF",
      } });

      map.addLayer({ id: "shop-labels", type: "symbol", source: "shops", layout: {
        "text-field": ["get", "name"],
        "text-font": ["Open Sans Semibold"],
        "text-size": ["interpolate", ["linear"], ["zoom"], 13, 10, 17, 13],
        "text-variable-anchor": ["left", "right", "top", "bottom"],
        "text-radial-offset": 0.8,
        "text-justify": "auto",
        "text-max-width": 9,
        "text-allow-overlap": true,
        "text-ignore-placement": true,
      }, paint: {
        "text-color": catColor,
        "text-halo-color": "#FFFFFF",
        "text-halo-width": 1.6,
      } });

      map.on("click", "shops", (e) => shopPopup(e.features[0]));
      map.on("click", "shop-labels", (e) => shopPopup(e.features[0]));
      map.on("click", "routes", (e) => {
        const p = e.features[0].properties;
        popup(e.lngLat, "#B4491A", "行車路線（推估）", p.from + " → " + p.to,
          '<div class="pp-note">約 ' + p.distance_km + " km・車程約 " + p.duration_min + " 分鐘（OSRM 推估，實際依領隊安排）</div>");
      });
      map.on("click", "transit", (e) => {
        const p = e.features[0].properties;
        const hw = p.headway_min ? "傍晚約每 " + p.headway_min + " 分一班" : "班距請以現場時刻表為準";
        popup(e.lngLat, "#1F6A72", p.mode === "tram" ? "市電" : "公車", (p.ref ? p.ref + " " : "") + (p.name || ""),
          '<div class="pp-note">往 ' + esc(p.to) + (p.operator ? "・" + esc(p.operator) : "") + "<br>" + hw + "</div>");
      });
      ["shops", "shop-labels", "routes", "transit"].forEach((l) => {
        map.on("mouseenter", l, () => { map.getCanvas().style.cursor = "pointer"; });
        map.on("mouseleave", l, () => { map.getCanvas().style.cursor = ""; });
      });
      setBasemap(state.basemap);
      setDay(state.day, false);
    };
    styleReady ? ready() : map.once("style.load", ready);
  }).catch((e) => console.error("data load failed", e));

  // first paint of static UI before data arrives
  setDay(state.day, false);
  renderAttrib();
  document.querySelectorAll("[data-basemap]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.basemap === state.basemap)));
})();
