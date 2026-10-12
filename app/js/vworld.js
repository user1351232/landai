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

function errorText(resp) {
  const err = resp.error || {};
  return `브이월드 오류 ${err.code || ""}: ${err.text || resp.status || ""}`.trim();
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

export function tileUrl(key, layer) {
  const ext = layer === "Satellite" ? "jpeg" : "png";
  return `https://api.vworld.kr/req/wmts/1.0.0/${key}/${layer}/{z}/{y}/{x}.${ext}`;
}
