// 브이월드 API (주소 → 좌표, 좌표 → 필지) — landai/apis/vworld.py 와 같은 동작
import { ApiError, getJson } from "./http.js";
import { getSetting } from "./settings.js";

export const PARCEL_LAYER = "LP_PA_CBND_BUBUN"; // 연속지적도
export const PARCEL_LABELS = {
  pnu: "필지고유번호(PNU)", addr: "지번 주소", jibun: "지번", bonbun: "본번", bubun: "부번",
  jiga: "개별공시지가(원/㎡)", gosi_year: "공시 연도", gosi_month: "공시 월",
};

export class VworldError extends Error {}

function params(extra) {
  const key = getSetting("VWORLD_KEY");
  if (!key) throw new VworldError("브이월드 키가 없습니다. 오른쪽 위 '설정'에서 키를 넣으세요.");
  return { key, domain: getSetting("VWORLD_DOMAIN") || "http://localhost", format: "json", ...extra };
}

async function get(target, p) {
  try {
    return await getJson(target, p);
  } catch (e) {
    throw new VworldError(`브이월드 ${e instanceof ApiError ? e.message : e}`);
  }
}

// 자주 나오는 키 오류에 해결 방법을 붙입니다.
const KEY_HINTS = {
  INCORRECT_KEY: (domain) => `키는 맞지만 등록 서비스 URL 이 다릅니다. 앱이 보낸 URL: ${domain}. ` +
    "브이월드 인증키 관리에 등록된 서비스 URL 을 '설정 → 브이월드 등록 서비스 URL' 에 글자 하나까지 똑같이 넣으세요.",
  INVALID_KEY: () => "브이월드에 없는 키입니다. '설정' 의 키가 브이월드 인증키 관리의 키와 같은지, " +
    "그 키의 활용 API 에 지오코더·2D데이터가 체크돼 있는지 확인하세요.",
  UNAVAILABLE_KEY: () => "키를 지금 쓸 수 없는 상태입니다. 브이월드 인증키 관리에서 상태와 만료일을 확인하세요.",
  OVER_REQUEST_LIMIT: () => "오늘 사용량을 넘었습니다. 내일 다시 시도하세요.",
};

function errorText(resp) {
  const err = resp.error || {};
  const base = `브이월드 오류 ${err.code || ""}: ${err.text || resp.status || ""}`.trim();
  const hint = KEY_HINTS[err.code];
  return hint ? `${base} → ${hint(getSetting("VWORLD_DOMAIN") || "http://localhost")}` : base;
}

export async function geocode(address) {
  for (const kind of ["road", "parcel"]) {
    const body = await get("vworld_address", params({
      service: "address", request: "getcoord", version: "2.0", crs: "epsg:4326",
      address, refine: "true", simple: "false", type: kind,
    }));
    const resp = body.response || {};
    if (resp.status === "OK") {
      const pt = resp.result.point;
      return { lon: Number(pt.x), lat: Number(pt.y), address: resp.refined?.text || address,
        type: kind === "road" ? "도로명" : "지번" };
    }
    if (resp.status === "ERROR") throw new VworldError(errorText(resp));
  }
  return null;
}

export async function parcelsAt(lon, lat) {
  const body = await get("vworld_data", params({
    service: "data", request: "GetFeature", data: PARCEL_LAYER,
    geomFilter: `POINT(${lon} ${lat})`, crs: "EPSG:4326",
    geometry: "true", attribute: "true", size: "10", page: "1",
  }));
  const resp = body.response || {};
  if (resp.status === "NOT_FOUND") return [];
  if (resp.status !== "OK") throw new VworldError(errorText(resp));
  return resp.result.featureCollection.features;
}

// 용도지역 레이어: 도시지역·관리지역·농림지역·자연환경보전지역
export const ZONE_LAYERS = ["LT_C_UQ111", "LT_C_UQ112", "LT_C_UQ113", "LT_C_UQ114"];

// 위치의 용도지역 도형. 세부 이름(uname)이 있는 것만 돌려줍니다. 없으면 null.
export async function zoneAt(lon, lat) {
  for (const layer of ZONE_LAYERS) {
    const body = await get("vworld_data", params({
      service: "data", request: "GetFeature", data: layer,
      geomFilter: `POINT(${lon} ${lat})`, crs: "EPSG:4326",
      geometry: "true", attribute: "true", size: "10", page: "1",
    }));
    const resp = body.response || {};
    if (resp.status === "NOT_FOUND") continue;
    if (resp.status !== "OK") throw new VworldError(errorText(resp));
    const named = (resp.result?.featureCollection?.features || []).filter((f) => f.properties?.uname);
    if (named.length) return { layer, feature: named[0], name: named[0].properties.uname };
  }
  return null;
}

// 토지이용계획 (국가중점 API). 필지 하나의 용도지역·지구·구역 목록 원본 항목을 돌려줍니다.
export async function landUse(pnu) {
  let body;
  try {
    body = await getJson("vworld_ned", params({ pnu, numOfRows: "100", pageNo: "1" }),
      { path: "getLandUseAttr" });
  } catch (e) {
    throw new VworldError(`브이월드 ${e instanceof ApiError ? e.message : e}`);
  }
  return nedItems(body);
}

// 국가중점 API 응답에서 항목 목록 꺼내기. 응답 모양이 두 가지라 둘 다 받습니다.
//   { landUses: { field: [...], totalCount, resultCode, resultMsg } }
//   { response: { status, fields: { field: [...] } } } 또는 { response: { status: "ERROR", error } }
export function nedItems(body) {
  if (body?.response?.status === "ERROR" || body?.response?.error) throw new VworldError(errorText(body.response));
  if (body?.response?.status === "NOT_FOUND") return [];
  const box = body?.response?.fields || body?.response
    || Object.values(body || {}).find((v) => v && typeof v === "object") || {};
  const code = box.resultCode ?? box.error?.code;
  if (code && !["OK", "0", "00", "INFO-000", "NORMAL_SERVICE"].includes(String(code))) {
    if (code === "NOT_FOUND" || code === "INFO-200") return [];
    throw new VworldError(errorText({ error: { code, text: box.resultMsg || box.error?.text || "" } }));
  }
  const field = box.field ?? box.fields?.field ?? [];
  return Array.isArray(field) ? field : [field];
}

export function tileUrl(key, layer) {
  const ext = layer === "Satellite" ? "jpeg" : "png";
  return `https://api.vworld.kr/req/wmts/1.0.0/${key}/${layer}/{z}/{y}/{x}.${ext}`;
}
