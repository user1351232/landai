// 시험 전용 가짜 Leaflet: 앱이 쓰는 함수만 흉내 내고, 그린 것을 window.__drawn 에 기록
(function () {
  const drawn = (window.__drawn = { tiles: [], geojson: [], markers: 0, view: null });
  const chain = (o) => Object.assign(o, { addTo(m) { return this; }, bindTooltip() { return this; } });
  const box = (el) => { el.style.background = "repeating-linear-gradient(45deg,#cfe3cf,#cfe3cf 10px,#e3efe3 10px,#e3efe3 20px)"; };
  window.L = {
    map(id) {
      box(document.getElementById(id));
      const handlers = {};
      return { setView(c, z) { drawn.view = [c, z]; this._z = z; return this; }, getZoom() { return this._z || 13; },
        removeLayer() {}, on(ev, fn) { handlers[ev] = fn; window.__mapClick = (lat, lng) => fn({ latlng: { lat, lng } }); return this; } };
    },
    control: { scale() { return chain({}); } },
    layerGroup() { return chain({ clearLayers() { drawn.geojson = []; } }); },
    tileLayer(url) { drawn.tiles.push(url); return chain({}); },
    geoJSON(f, opt) { drawn.geojson.push(opt.style); return chain({}); },
    marker() { drawn.markers++; return chain({}); },
  };
})();
