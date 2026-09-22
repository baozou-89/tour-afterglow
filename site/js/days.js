// Day definitions. The trip start date lives only here and is never rendered on the page.
window.TRIP = {
  // Day1 in Japan time (JST). Used only to auto-select the current day.
  start: "2026-09-23T00:00:00+09:00",
  days: {
    1: { title: "Day 1 · 福岡市區", area: "據點 ↔ 天神 ↔ 中洲 ↔ 博多站，晚餐自理（屋台）",
         bounds: [[130.388, 33.576], [130.455, 33.598]], food: true },
    2: { title: "Day 2 · 熊本", area: "上通・下通・新市街 ↔ 熊本站，晚餐自理",
         bounds: [[130.684, 32.786], [130.716, 32.812]], food: true },
    3: { title: "Day 3 · 別府", area: "據點 ↔ 別府站（晚餐為飯店自助餐）",
         bounds: [[131.470, 33.275], [131.507, 33.320]] },
    4: { title: "Day 4 · 福岡", area: "LaLaport 館內，回程後 據點 ↔ 天神・博多",
         bounds: [[130.388, 33.560], [130.455, 33.598]] },
    5: { title: "Day 5 · 北九州", area: "門司港懷舊區、THE OUTLETS 北九州＋AEON MALL",
         bounds: [[130.795, 33.860], [130.972, 33.952]] },
  },
};
