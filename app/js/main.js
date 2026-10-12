// 앱 화면 — 스마트폰(Capacitor)과 윈도우(Tauri)가 같은 코드를 씁니다
import { analyze } from "./pipeline.js";
import { REGIONS } from "./regions.js";
import { getSetting, setSetting } from "./settings.js";
import { platform } from "./http.js";
import * as vworld from "./vworld.js";

const $ = (sel) => document.querySelector(sel);
const PLATFORM_KO = { "windows-app": "윈도우 앱", "mobile-app": "스마트폰 앱", browser: "웹 브라우저" };
const GRADE_COLOR = { 확정: "#1a7f37", 복원: "#1f6feb", 추정: "#9a6700", 미연결: "#cf222e" };

const state = { mode: "coord", point: null, choice: null, result: null, regionId: "jeonju" };
let map, baseLayers = [], parcelLayer, marker;

// ---------- 작은 도우미 ----------
function el(tag, attrs = {}, ...children) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v);
  }
  for (const c of children.flat()) n.append(c instanceof Node ? c : document.createTextNode(String(c ?? "")));
  return n;
}
const region = () => REGIONS[state.regionId];

async function waitForLeaflet(ms = 10000) {
  const start = Date.now();
  while (!globalThis.L) {
    if (Date.now() - start > ms) throw new Error("지도 라이브러리를 불러오지 못했습니다");
    await new Promise((r) => setTimeout(r, 100));
  }
  return globalThis.L;
}

// ---------- 지도 ----------
function applyBasemap() {
  const L = globalThis.L;
  baseLayers.forEach((l) => map.removeLayer(l));
  baseLayers = [];
  const key = getSetting("VWORLD_KEY");
  const choice = getSetting("BASEMAP") || "Satellite";
  if (key && choice !== "osm") {
    baseLayers.push(L.tileLayer(vworld.tileUrl(key, choice), { maxZoom: 19, attribution: "© VWorld" }));
    if (choice === "Satellite")
      baseLayers.push(L.tileLayer(vworld.tileUrl(key, "Hybrid"), { maxZoom: 19 }));
  } else {
    baseLayers.push(L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",
      { maxZoom: 19, attribution: "© OpenStreetMap" }));
  }
  baseLayers.forEach((l) => l.addTo(map));
}

function drawResult() {
  const L = globalThis.L;
  parcelLayer.clearLayers();
  if (marker) { map.removeLayer(marker); marker = null; }
  const r = state.result;
  if (r?.parcels?.length) {
    r.parcels.forEach((f, i) => {
      const chosen = r.parcel === f;
      L.geoJSON(f, {
        style: { color: chosen ? GRADE_COLOR[r.grade] : "#888", weight: chosen ? 3 : 1.5,
          fillOpacity: chosen ? 0.25 : 0.05, dashArray: chosen ? null : "5 5" },
      }).bindTooltip(f.properties?.addr || `후보 ${i + 1}`).addTo(parcelLayer);
    });
  }
  if (state.point) {
    marker = L.marker([state.point[1], state.point[0]]).addTo(map);
    map.setView([state.point[1], state.point[0]], Math.max(map.getZoom(), 18));
  }
}

// ---------- 결과 패널 ----------
function renderPanel() {
  const panel = $("#panel");
  panel.replaceChildren();
  const r = state.result;
  if (!r) { panel.append(el("p", { class: "placeholder" }, "위치를 입력하고 '분석하기'를 누르세요.")); return; }

  const last = r.log[r.log.length - 1]?.결과 || "";
  if (r.status === "outside") panel.append(el("div", { class: "msg error" }, `${region().name} 범위 밖입니다. 지역을 바꾸거나 위치를 다시 입력하세요.`));
  else if (r.status === "error") panel.append(el("div", { class: "msg error" }, last));
  else if (r.status === "no_parcel") panel.append(el("div", { class: "msg warn" }, "이 위치에서 필지를 찾지 못했습니다. 도로나 하천 위일 수 있어요."));
  else if (r.status === "multiple") {
    panel.append(el("div", { class: "msg warn" }, "후보 필지가 여러 개입니다. 분석할 필지를 고르세요."));
    panel.append(el("div", { class: "candidates" }, r.parcels.map((f, i) =>
      el("button", { type: "button", onclick: () => { state.choice = i; run(); } },
        f.properties?.addr || `후보 ${i + 1}`))));
  } else {
    const p = r.parcel.properties || {};
    let jiga = "정보 없음";
    const jn = Number(p.jiga);
    if (p.jiga !== undefined && p.jiga !== "" && Number.isFinite(jn)) jiga = `${Math.round(jn).toLocaleString("ko-KR")} 원/㎡`;
    panel.append(
      el("div", {}, el("span", { class: `badge grade-${r.grade}` }, `연결 확신도: ${r.grade}`)),
      el("h2", {}, p.addr || "필지"),
      el("div", { class: "metrics" },
        el("div", { class: "metric" }, el("div", { class: "label" }, "면적 (EPSG:5186)"),
          el("div", { class: "value" }, `${r.area_m2.toLocaleString("ko-KR")} ㎡`)),
        el("div", { class: "metric" }, el("div", { class: "label" }, "개별공시지가"), el("div", { class: "value" }, jiga))),
      el("div", { class: "code" }, r.pnu?.pnu || r.pnu?.raw || ""),
      el("table", {}, el("tbody", {}, Object.entries(p).map(([k, v]) =>
        el("tr", {}, el("th", {}, vworld.PARCEL_LABELS[k] || k), el("td", {}, v))))),
    );
  }

  panel.append(el("h2", {}, "분석 이력서"));
  panel.append(el("table", { class: "log" },
    el("thead", {}, el("tr", {}, ["시각", "단계", "판정", "결과"].map((h) => el("th", {}, h)))),
    el("tbody", {}, r.log.map((s) => el("tr", {}, [s.시각, s.단계, s.판정, s.결과].map((v) => el("td", {}, v)))))));
  const report = JSON.stringify({ ...r, parcels: undefined, platform: platform() }, null, 2);
  panel.append(el("div", { class: "row" },
    el("button", { type: "button", onclick: () => copyText(report) }, "이력서 복사"),
    el("button", { type: "button", onclick: () => saveText(report, "analysis_report.json") }, "이력서 저장")));
}

async function copyText(text) {
  try { await navigator.clipboard.writeText(text); alert("분석 이력서를 복사했습니다."); }
  catch { alert("복사하지 못했습니다. '이력서 저장'을 써 주세요."); }
}
function saveText(text, name) {
  const a = el("a", { href: URL.createObjectURL(new Blob([text], { type: "application/json" })), download: name });
  document.body.append(a); a.click(); a.remove();
}

// ---------- 실행 ----------
async function run() {
  const btn = $("#run");
  btn.disabled = true; btn.textContent = "분석 중…";
  try {
    state.result = await analyze(state.point[0], state.point[1], region(),
      { choice: state.choice, fetchParcels: vworld.parcelsAt });
  } finally {
    btn.disabled = false; btn.textContent = "분석하기";
  }
  renderPanel(); drawResult();
}

function showError(message) {
  state.result = null;
  $("#panel").replaceChildren(el("div", { class: "msg error" }, message));
}

async function onSubmit(e) {
  e?.preventDefault();
  state.choice = null;
  try {
    if (state.mode === "coord") {
      const lat = Number($("#lat").value), lon = Number($("#lon").value);
      if (!Number.isFinite(lat) || !Number.isFinite(lon) || !$("#lat").value || !$("#lon").value)
        return showError("위도와 경도를 숫자로 입력하세요. 예: 35.8242, 127.1480");
      state.point = [lon, lat];
    } else if (state.mode === "address") {
      const q = $("#address").value.trim();
      if (!q) return showError("주소를 입력하세요.");
      const g = await vworld.geocode(q);
      if (!g) return showError("주소를 찾지 못했습니다. 시·구 이름부터 적어 보세요.");
      state.point = [g.lon, g.lat];
    } else if (state.mode === "gps") {
      state.point = await new Promise((resolve, reject) => {
        if (!navigator.geolocation) return reject(new Error("이 기기에서는 위치를 쓸 수 없습니다."));
        navigator.geolocation.getCurrentPosition(
          (p) => resolve([p.coords.longitude, p.coords.latitude]),
          (err) => reject(new Error(`위치를 가져오지 못했습니다 (${err.message}). 위치 권한을 허용했는지 확인하세요.`)),
          { enableHighAccuracy: true, timeout: 15000 });
      });
    } else {
      return showError("지도에서 분석할 곳을 누르세요.");
    }
    await run();
  } catch (err) {
    showError(err.message || String(err));
  }
}

// ---------- 설정 ----------
function openSettings() {
  $("#set-vworld-key").value = localStorageValue("VWORLD_KEY");
  $("#set-vworld-domain").value = getSetting("VWORLD_DOMAIN");
  $("#set-basemap").value = getSetting("BASEMAP") || "Satellite";
  const hasKey = Boolean(getSetting("VWORLD_KEY"));
  $("#platform-info").textContent =
    `실행 환경: ${PLATFORM_KO[platform()]} · 브이월드 키: ${hasKey ? "있음" : "없음"}`;
  $("#settings").showModal();
}
function localStorageValue(name) {
  try { return localStorage.getItem("landai." + name) || ""; } catch { return ""; }
}
function saveSettings() {
  setSetting("VWORLD_KEY", $("#set-vworld-key").value);
  setSetting("VWORLD_DOMAIN", $("#set-vworld-domain").value);
  setSetting("BASEMAP", $("#set-basemap").value);
  applyBasemap();
}

// ---------- 시작 ----------
async function init() {
  const sel = $("#region");
  for (const r of Object.values(REGIONS)) sel.append(el("option", { value: r.id }, r.name));
  sel.addEventListener("change", () => {
    state.regionId = sel.value;
    const [lon, lat] = region().center;
    map?.setView([lat, lon], 13);
  });

  document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => {
    state.mode = t.dataset.mode;
    document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === t));
    document.querySelectorAll(".mode").forEach((m) => m.classList.toggle("hidden", m.dataset.mode !== state.mode));
    $("#run").classList.toggle("hidden", state.mode === "click");
  }));
  $("#input-form").addEventListener("submit", onSubmit);
  $("#open-settings").addEventListener("click", openSettings);
  $("#save-settings").addEventListener("click", saveSettings);

  const [lon, lat] = region().center;
  $("#lat").value = lat; $("#lon").value = lon;

  try {
    const L = await waitForLeaflet();
    map = L.map("map", { zoomControl: true }).setView([lat, lon], 13);
    L.control.scale({ imperial: false }).addTo(map);
    parcelLayer = L.layerGroup().addTo(map);
    applyBasemap();
    map.on("click", (e) => {
      if (state.mode !== "click") return;
      state.point = [e.latlng.lng, e.latlng.lat];
      state.choice = null;
      run().catch((err) => showError(err.message || String(err)));
    });
  } catch (err) {
    showError(err.message);
  }

  if (!getSetting("VWORLD_KEY"))
    $("#panel").replaceChildren(el("div", { class: "msg warn" },
      "브이월드 키가 없습니다. 오른쪽 위 '설정'에서 키를 넣으세요."));
}

init();
