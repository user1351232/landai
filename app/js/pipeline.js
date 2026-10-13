// 위치 하나를 받아 분석 단계를 순서대로 실행하고 단계마다 이력을 남깁니다
// (landai/pipeline.py 와 같은 단계·판정)
import * as geo from "./geo.js";
import { standardize } from "./pnu.js";
import { parseJimok } from "./parcel.js";

const KO = { pass: "통과", warn: "경고", fail: "실패" };

function now() {
  const d = new Date();
  return [d.getHours(), d.getMinutes(), d.getSeconds()].map((n) => String(n).padStart(2, "0")).join(":");
}

export async function analyze(lon, lat, region, { choice = null, fetchParcels } = {}) {
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
  return out;
}
