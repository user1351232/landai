// 국내 공공 API 호출.
// - 윈도우 앱(Tauri): 앱 안의 Rust 명령(http_get)이 이 컴퓨터에서 직접 호출 (브라우저 제한 없음)
// - 안드로이드 앱(Capacitor): CapacitorHttp 가 fetch 를 휴대폰의 네이티브 요청으로 바꿔 줌
// - 일반 브라우저: 그냥 fetch (브이월드가 막을 수 있음 → 앱으로 실행 안내)
// 어느 경우든 요청은 사용자의 기기(국내)에서 나가며, 해외 서버를 거치지 않습니다.

export const TARGET_URLS = {
  vworld_data: "https://api.vworld.kr/req/data",
  vworld_address: "https://api.vworld.kr/req/address",
  vworld_search: "https://api.vworld.kr/req/search",
  juso: "https://business.juso.go.kr/addrlink/addrLinkApi.do",
};
// 브이월드 국가중점(NED) API: 정해진 기능 이름만 허용
export const NED_BASE = "https://api.vworld.kr/ned/data/";
export const NED_OPS = ["getLandUseAttr", "ladfrlList", "getLandCharacteristics", "getIndvdLandPriceAttr"];
const DATA_GO_KR = "https://apis.data.go.kr/";
const DATA_PATH_RE = /^[0-9]{7}\/[A-Za-z0-9_]+(\/[A-Za-z0-9_]+){0,3}$/;

export class ApiError extends Error {}

export function buildUrl(target, params, path) {
  let base;
  if (target in TARGET_URLS) base = TARGET_URLS[target];
  else if (target === "datagokr" && path && DATA_PATH_RE.test(path)) base = DATA_GO_KR + path;
  else if (target === "vworld_ned" && NED_OPS.includes(path)) base = NED_BASE + path;
  else throw new ApiError(`허용되지 않은 대상: ${target}`);
  const qs = new URLSearchParams(params).toString();
  return qs ? `${base}?${qs}` : base;
}

export function platform() {
  if (globalThis.__TAURI__?.core?.invoke) return "windows-app";
  if (globalThis.Capacitor?.isNativePlatform?.()) return "mobile-app";
  return "browser";
}

export async function getJson(target, params, { path = null } = {}) {
  const p = Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)]));
  const where = platform();
  let text;
  try {
    if (where === "windows-app") {
      text = await globalThis.__TAURI__.core.invoke("http_get", { target, params: p, path });
    } else {
      const r = await fetch(buildUrl(target, p, path));
      if (!r.ok) throw new ApiError(`HTTP ${r.status}`);
      text = await r.text();
    }
  } catch (e) {
    if (e instanceof ApiError) throw e;
    const hint = where === "browser"
      ? " 일반 브라우저에서는 브이월드 호출이 막힐 수 있어요. 윈도우·안드로이드 앱으로 실행하세요."
      : " 인터넷 연결을 확인하세요.";
    throw new ApiError(`접속 실패 (${e?.message || e}).${hint}`);
  }
  try {
    return JSON.parse(text);
  } catch {
    throw new ApiError("응답이 JSON 이 아닙니다. 키와 등록 URL 을 확인하세요.");
  }
}
