// 용도지역 판정: 두 자료(토지이용계획, 용도지역 레이어)를 맞춰 보고 건축 한도를 계산합니다.
//
// - 토지이용계획 (브이월드 국가중점 API getLandUseAttr): 필지번호로 조회. 토지이음의 토지이용계획확인서와 같은 자료.
//   한 필지에 용도지역·지구·구역 여러 개가 "포함/저촉/접합" 으로 붙어 옵니다.
// - 용도지역 레이어 (브이월드 2D데이터 LT_C_UQ111~114): 위치로 조회. 경계 도형이 있어 지도에 그립니다.

// 국토계획법 시행령 제84조(건폐율)·제85조(용적률)의 상한 (단위 %). 시·군 조례는 이보다 낮게 정할 수 있습니다.
export const ZONES = {
  "제1종전용주거지역": { group: "주거", bcr: 50, far: 100 },
  "제2종전용주거지역": { group: "주거", bcr: 50, far: 150 },
  "제1종일반주거지역": { group: "주거", bcr: 60, far: 200 },
  "제2종일반주거지역": { group: "주거", bcr: 60, far: 250 },
  "제3종일반주거지역": { group: "주거", bcr: 50, far: 300 },
  "준주거지역": { group: "주거", bcr: 70, far: 500 },
  "중심상업지역": { group: "상업", bcr: 90, far: 1500 },
  "일반상업지역": { group: "상업", bcr: 80, far: 1300 },
  "근린상업지역": { group: "상업", bcr: 70, far: 900 },
  "유통상업지역": { group: "상업", bcr: 80, far: 1100 },
  "전용공업지역": { group: "공업", bcr: 70, far: 300 },
  "일반공업지역": { group: "공업", bcr: 70, far: 350 },
  "준공업지역": { group: "공업", bcr: 70, far: 400 },
  "보전녹지지역": { group: "녹지", bcr: 20, far: 80 },
  "생산녹지지역": { group: "녹지", bcr: 20, far: 100 },
  "자연녹지지역": { group: "녹지", bcr: 20, far: 100 },
  "보전관리지역": { group: "관리", bcr: 20, far: 80 },
  "생산관리지역": { group: "관리", bcr: 20, far: 80 },
  "계획관리지역": { group: "관리", bcr: 40, far: 100 },
  "농림지역": { group: "농림", bcr: 20, far: 80 },
  "자연환경보전지역": { group: "자연환경보전", bcr: 20, far: 80 },
};
export const LAW_SOURCE = "국토계획법 시행령 제84조·제85조 상한";

// 지도·배지 색 (도시계획 도면의 관례 색에 가깝게)
export const GROUP_COLOR = {
  주거: "#e3b505", 상업: "#e5484d", 공업: "#8e4ec6", 녹지: "#30a46c",
  관리: "#7cb342", 농림: "#a1887f", 자연환경보전: "#12a594", 기타: "#8b8d98",
};

const norm = (s) => String(s ?? "").replace(/\s+/g, "");

export function zoneInfo(name) {
  const z = ZONES[norm(name)];
  return z ? { name: norm(name), ...z } : null;
}

// 토지이용계획 항목 하나의 종류: 용도지역 / 용도지구 / 용도구역·기타
export function kindOf(name) {
  const n = norm(name);
  if (ZONES[n] || n === "도시지역" || n === "관리지역") return "용도지역";
  if (n.endsWith("지구")) return "지구";
  return "구역·기타";
}

const CONFLICT = { 1: "포함", 2: "저촉", 3: "접합" };

// 토지이용계획 응답 → [{ name, code, conflict, kind }]
export function parseLandUse(items) {
  return (items || []).map((it) => {
    const name = String(it.prposAreaDstrcCodeNm || it.prposAreaDstrcCode || "").trim();
    return {
      name, code: String(it.prposAreaDstrcCode || ""), kind: kindOf(name),
      conflict: String(it.cnflcAtNm || CONFLICT[it.cnflcAt] || it.cnflcAt || "").trim(),
    };
  }).filter((x) => x.name);
}

// 지역 설정에 조례 값이 있으면 그 값을, 없으면 법정 상한을 씁니다.
export function limitsFor(name, region) {
  const z = zoneInfo(name);
  if (!z) return null;
  const ord = region?.ordinance || {};
  const far = ord.far?.[z.name], bcr = ord.bcr?.[z.name];
  return {
    bcr: bcr ?? z.bcr, far: far ?? z.far,
    bcrSource: bcr != null ? ord.source : LAW_SOURCE,
    farSource: far != null ? ord.source : LAW_SOURCE,
    lawBcr: z.bcr, lawFar: z.far,
  };
}

// 두 자료를 합쳐 판정. landUse: parseLandUse 결과 또는 null(조회 실패), layerName: 레이어의 uname 또는 null
export function judge(landUse, layerName, areaM2, region) {
  const main = (landUse || []).filter((x) => zoneInfo(x.name));
  const names = [...new Set(main.map((x) => zoneInfo(x.name).name))];
  const layer = layerName ? norm(layerName) : null;
  let agree = "unknown";
  if (names.length && layer) agree = names.includes(layer) ? "match" : "differ";
  else if (layer && landUse === null) agree = "layer_only";
  else if (names.length && !layer) agree = "plan_only";

  // 기준 용도지역: 토지이용계획에서 '포함' 인 것 → 아무거나 → 레이어 값
  const primaryName = (main.find((x) => x.conflict === "포함") || main[0])?.name || layer;
  const primary = primaryName ? zoneInfo(primaryName) : null;
  const split = names.length > 1;
  const lim = primary ? limitsFor(primary.name, region) : null;
  const build = lim && !split && areaM2 ? {
    maxFootprint: Math.round(areaM2 * lim.bcr) / 100,
    maxFloorArea: Math.round(areaM2 * lim.far) / 100,
  } : null;
  return {
    zone: primary ? primary.name : null,
    group: primary ? primary.group : null,
    zones: names, split, agree, limits: lim, build,
    districts: (landUse || []).filter((x) => x.kind === "지구"),
    others: (landUse || []).filter((x) => x.kind === "구역·기타"),
  };
}
