// 위치 하나를 받아 분석 단계를 순서대로 실행하고 단계마다 이력을 남깁니다
// (landai/pipeline.py 와 같은 단계·판정)
import * as geo from "./geo.js";
import { standardize } from "./pnu.js";
import { parseJimok } from "./parcel.js";
import { judge, parseLandUse } from "./zoning.js";

const KO = { pass: "통과", warn: "경고", fail: "실패" };

function now() {
  const d = new Date();
  return [d.getHours(), d.getMinutes(), d.getSeconds()].map((n) => String(n).padStart(2, "0")).join(":");
}

export async function analyze(lon, lat, region, { choice = null, fetchParcels, fetchLandUse, fetchZone } = {}) {
  const log = [];
  const step = (단계, 도구, status, 결과) => log.push({ 시각: now(), 단계, 도구, 판정: KO[status], 결과 });
  const out = { input: { lon, lat }, region: region.id, status: "ok", parcels: [], parcel: null,
    pnu: null, area_m2: null, grade: "미연결", log };

  // 1. 위치 확인
  if (!geo.inRegion(lon, lat, region)) {
    step("위치 확인", "inRegion", "fail", `(${lat.toFixed(5)}, ${lon.toFixed(5)}) 은 ${region.name} 범위 밖. 지원 지역이 아님`);
    out.status = "outside";
    return out;
  }
  step("위치 확인", "inRegion", "pass", `${region.name} 범위 안`);

  // 2. 필지 조회
  let feats;
  try {
    feats = await fetchParcels(lon, lat);
  } catch (e) {
    step("필지 조회", "vworld.parcelsAt", "fail", e.message || String(e));
    out.status = "error";
    return out;
  }
  out.parcels = feats;
  if (!feats.length) {
    step("필지 조회", "vworld.parcelsAt", "warn", "필지 없음. 도로·하천 위이거나 지적도에 없는 위치");
    out.status = "no_parcel";
    return out;
  }
  if (feats.length > 1 && choice === null) {
    step("필지 조회", "vworld.parcelsAt", "warn", `후보 필지 ${feats.length}개. 사용자 선택 필요 (되묻기)`);
    out.status = "multiple";
    return out;
  }
  const feat = feats[choice ?? 0];
  out.parcel = feat;
  const props = feat.properties || {};
  const jm = parseJimok(props.jibun);
  out.jimok = jm ? jm.name : null;
  step("필지 조회", "vworld.parcelsAt", "pass",
    `${props.addr || props.jibun || "필지"}${jm ? ` (지목: ${jm.name})` : ""} 찾음`);

  // 3. 필지번호 검사
  const r = standardize(props.pnu, { legacySido: region.legacy_sido_code, currentSido: region.sido_code });
  out.pnu = { raw: r.raw, pnu: r.pnu, status: r.status, note: r.note };
  const pnuOk = ["ok", "recoded", "restored"].includes(r.status);
  step("필지번호 검사", "pnu.standardize", r.status === "ok" ? "pass" : pnuOk ? "warn" : "fail",
    `${r.status} ${r.pnu || r.raw} ${r.note}`.trim());

  // 4. 위치 교차 확인, 5. 면적 (EPSG:5186)
  const inside = geo.contains(feat.geometry, lon, lat);
  step("위치 교차 확인", "geo.contains", inside ? "pass" : "warn",
    inside ? "입력 좌표가 필지 경계 안에 있음" : "입력 좌표가 필지 경계 밖");
  out.area_m2 = Math.round(geo.areaM2(feat.geometry) * 10) / 10;
  step("면적 계산", "geo.areaM2 (EPSG:5186)", "pass", `${out.area_m2.toLocaleString("ko-KR")} ㎡`);

  // 6. 확신도
  out.grade = pnuOk && inside ? ({ ok: "확정", recoded: "확정", restored: "복원" })[r.status] : "추정";
  step("확신도 판정", "rules", out.grade === "확정" ? "pass" : "warn", out.grade);

  // 7~9. 용도지역 (조회 함수가 주어졌을 때만)
  if (fetchLandUse || fetchZone) await zoningSteps(out, step, feat, lon, lat, inside, region, fetchLandUse, fetchZone);
  return out;
}

// 필지 안쪽의 한 점: 입력 좌표가 필지 안이면 그대로, 아니면 경계 꼭짓점 평균
function innerPoint(geom, lon, lat, inside) {
  if (inside) return [lon, lat];
  const ring = geom?.type === "MultiPolygon" ? geom.coordinates?.[0]?.[0] : geom?.coordinates?.[0];
  if (!ring?.length) return [lon, lat];
  const n = ring.length - 1 || 1;
  const c = ring.slice(0, n).reduce((a, p) => [a[0] + p[0] / n, a[1] + p[1] / n], [0, 0]);
  return geo.contains(geom, c[0], c[1]) ? c : [lon, lat];
}

async function zoningSteps(out, step, feat, lon, lat, inside, region, fetchLandUse, fetchZone) {
  const [plon, plat] = innerPoint(feat.geometry, lon, lat, inside);
  const pnu = out.pnu?.pnu;
  const [plan, layer] = await Promise.allSettled([
    pnu && fetchLandUse ? fetchLandUse(pnu) : Promise.reject(new Error(pnu ? "조회 기능 없음" : "필지번호 없음")),
    fetchZone ? fetchZone(plon, plat) : Promise.reject(new Error("조회 기능 없음")),
  ]);

  // 7. 토지이용계획
  let landUse = null;
  if (plan.status === "fulfilled") {
    landUse = parseLandUse(plan.value);
    const zones = landUse.filter((x) => x.kind === "용도지역").map((x) => `${x.name}(${x.conflict || "?"})`);
    step("용도지역 조회", "vworld.landUse (토지이용계획)", landUse.length ? "pass" : "warn",
      landUse.length ? `${zones.join(", ") || "용도지역 없음"} · 지구 ${landUse.filter((x) => x.kind === "지구").length}건 · ` +
        `구역·기타 ${landUse.filter((x) => x.kind === "구역·기타").length}건` : "토지이용계획 항목 없음");
  } else {
    step("용도지역 조회", "vworld.landUse (토지이용계획)", "warn", `조회 실패: ${plan.reason?.message || plan.reason}`);
  }

  // 8. 용도지역 레이어와 교차 확인
  const zoneHit = layer.status === "fulfilled" ? layer.value : null;
  out.zoneFeature = zoneHit?.feature || null;
  const z = judge(landUse, zoneHit?.name || null, out.area_m2, region);
  out.zoning = { ...z, layer: zoneHit?.layer || null, layerName: zoneHit?.name || null };
  const layerErr = layer.status === "rejected" ? `레이어 조회 실패: ${layer.reason?.message || layer.reason}` : "레이어에 없음";
  const msg = {
    match: ["pass", `두 자료 일치: ${z.zone}`],
    differ: ["warn", `토지이용계획 ${z.zones.join(", ")} / 레이어 ${zoneHit?.name}. 용도지역 경계에 걸친 필지일 수 있음`],
    layer_only: ["warn", `레이어 값만 있음: ${z.zone}`],
    plan_only: ["warn", `토지이용계획 값만 있음: ${z.zone} (${layerErr})`],
    unknown: ["fail", `용도지역을 확인하지 못함 (${layerErr})`],
  }[z.agree];
  step("용도지역 교차 확인", "vworld.zoneAt (LT_C_UQ111~114)", msg[0], msg[1]);

  // 9. 건축 한도
  if (z.limits) {
    const L = z.limits;
    const src = L.bcrSource === L.farSource ? L.farSource : `건폐율 ${L.bcrSource}, 용적률 ${L.farSource}`;
    if (z.split) {
      step("건축 한도 계산", "zoning.limitsFor", "warn",
        `용도지역 ${z.zones.length}개에 걸침 → 면적 비율로 나눠 계산해야 함. 기준(${z.zone}) 건폐율 ${L.bcr}% · 용적률 ${L.far}%`);
    } else {
      const f = (v) => v.toLocaleString("ko-KR", { maximumFractionDigits: 1 });
      step("건축 한도 계산", "zoning.limitsFor", "pass",
        `건폐율 ${L.bcr}% · 용적률 ${L.far}% → 최대 건축면적 ${f(z.build.maxFootprint)} ㎡, 최대 연면적 ${f(z.build.maxFloorArea)} ㎡ (${src})`);
    }
  }
}
