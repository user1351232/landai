// 필지 속성 정리: 지목 꺼내기, 표에 보일 순서와 이름
// 연속지적도의 jibun 값은 "568-1 대", "산 12 임" 처럼 끝에 지목 부호가 붙어 옵니다.

// 지목 부호 → 정식 이름 (공간정보관리법 시행령 제58조, 28개)
export const JIMOK = {
  전: "전", 답: "답", 과: "과수원", 목: "목장용지", 임: "임야", 광: "광천지", 염: "염전",
  대: "대", 장: "공장용지", 학: "학교용지", 차: "주차장", 주: "주유소용지", 창: "창고용지",
  도: "도로", 철: "철도용지", 제: "제방", 천: "하천", 구: "구거", 유: "유지", 양: "양어장",
  수: "수도용지", 공: "공원", 체: "체육용지", 원: "유원지", 종: "종교용지", 사: "사적지",
  묘: "묘지", 잡: "잡종지",
};

// "568-1 대" → { code: "대", name: "대", lot: "568-1" }. 지목이 없으면 null.
export function parseJimok(jibun) {
  const m = String(jibun ?? "").trim().match(/^(.*?\d[\d-]*)\s*([가-힣])$/);
  if (!m || !JIMOK[m[2]]) return null;
  return { code: m[2], name: JIMOK[m[2]], lot: m[1].trim() };
}

function stripZeros(v) {
  const s = String(v ?? "").trim();
  return /^\d+$/.test(s) ? String(Number(s)) : s;
}

function won(v) {
  const n = Number(v);
  return v !== undefined && v !== "" && Number.isFinite(n) ? `${Math.round(n).toLocaleString("ko-KR")} 원/㎡` : "";
}

// 화면 표에 보일 [이름, 값] 목록. 정해진 순서 뒤에 모르는 속성을 그대로 붙입니다.
export function parcelRows(props = {}) {
  const jm = parseJimok(props.jibun);
  const rows = [
    ["지번 주소", props.addr],
    ["지번", jm ? jm.lot : props.jibun],
    ["지목", jm ? (jm.name === jm.code ? jm.name : `${jm.name} (${jm.code})`) : ""],
    ["본번", stripZeros(props.bonbun)],
    ["부번", stripZeros(props.bubun)],
    ["개별공시지가", won(props.jiga)],
    ["공시 기준", props.gosi_year ? `${props.gosi_year}년 ${props.gosi_month ? Number(props.gosi_month) + "월" : ""}`.trim() : ""],
    ["필지고유번호(PNU)", props.pnu],
  ];
  const known = new Set(["addr", "jibun", "bonbun", "bubun", "jiga", "gosi_year", "gosi_month", "pnu"]);
  for (const [k, v] of Object.entries(props)) if (!known.has(k)) rows.push([k, v]);
  return rows.filter(([, v]) => v !== undefined && v !== null && String(v) !== "");
}
