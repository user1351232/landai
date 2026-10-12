// 필지고유번호(PNU) 표준화 — landai/pnu.py 와 같은 규칙
// 19자리 = 법정동코드 10 + 산구분 1 (1 일반, 2 산) + 본번 4 + 부번 4

const SCI_RE = /^\s*\d(\.\d+)?[eE]\+?\d+\s*$/;
const JIBUN_RE = /(산)?\s*(\d+)(?:\s*-\s*(\d+))?/g;

export function clean(raw) {
  if (raw === null || raw === undefined) return "";
  let s = String(raw).trim();
  if (s.endsWith(".0")) s = s.slice(0, -2);
  return s.replace(/\D/g, "");
}

export function isValid19(p) {
  return p.length === 19 && /^\d+$/.test(p) && "12".includes(p[10]) && p.slice(11, 15) !== "0000";
}

/** '산 12-3' → ['2','0012','0003']. 동 이름의 숫자('효자동1가')를 피하려고 마지막 숫자 묶음을 씀 */
export function parseJibun(text) {
  if (!text) return null;
  const matches = [...String(text).matchAll(JIBUN_RE)];
  if (!matches.length) return null;
  const m = matches[matches.length - 1];
  const pad = (v) => String(v || "0").padStart(4, "0").slice(-4);
  return [m[1] ? "2" : "1", pad(m[2]), pad(m[3])];
}

export function recodeSido(p, legacy, current) {
  if (legacy && current && p.startsWith(legacy)) return [current + p.slice(legacy.length), true];
  return [p, false];
}

function candidates18(s) {
  const c = [
    s.slice(0, 10) + "1" + s.slice(10),
    s.slice(0, 10) + "2" + s.slice(10),
    s.slice(0, 11) + "0" + s.slice(11),
    s.slice(0, 15) + "0" + s.slice(15),
  ];
  return [...new Set(c)].filter(isValid19);
}

/**
 * @returns {{raw:string, pnu:string|null, status:string, rule:string|null, note:string, candidates:string[]}}
 * status: ok | recoded | restored | ambiguous | invalid | sci_notation | empty
 */
export function standardize(raw, { legacySido, currentSido, knownPnus, dongCodes, jibunText } = {}) {
  const rawS = raw === null || raw === undefined ? "" : String(raw);
  const res = (pnu, status, rule = null, note = "", candidates = []) =>
    ({ raw: rawS, pnu, status, rule, note, candidates });

  if (!rawS.trim() || rawS.trim().toLowerCase() === "nan") return res(null, "empty");
  if (SCI_RE.test(rawS))
    return res(null, "sci_notation", "STD-PNU-03", "엑셀 지수 표기로 뒷자리가 사라짐. 원본을 텍스트로 다시 받아야 함");

  const s = clean(rawS);
  const jb = parseJibun(jibunText);
  const recode = (p) => recodeSido(p, legacySido, currentSido);
  const plausible = (p) => {
    if (dongCodes && !dongCodes.has(p.slice(0, 10))) return false;
    if (jb && (p[10] !== jb[0] || p.slice(11, 15) !== jb[1] || p.slice(15, 19) !== jb[2])) return false;
    return true;
  };

  if (s.length === 19) {
    const [p, changed] = recode(s);
    if (!isValid19(p)) return res(null, "invalid", "STD-PNU-01", "19자리지만 산구분·본번 형식 오류");
    if (changed) return res(p, "recoded", "STD-SIDO-01", `시도코드 ${legacySido}→${currentSido}`);
    return res(p, "ok", "STD-PNU-01");
  }
  if (s.length === 18) {
    let c = [...new Set(candidates18(s).map((x) => recode(x)[0]))].filter(plausible);
    if (knownPnus) {
      const hits = c.filter((x) => knownPnus.has(x));
      if (hits.length) c = hits;
    }
    if (c.length === 1) return res(c[0], "restored", "STD-PNU-02", "18자리 손상 복구", c);
    if (!c.length) return res(null, "invalid", "STD-PNU-02", "복구 후보 없음");
    return res(null, "ambiguous", "STD-PNU-02", `복구 후보 ${c.length}개, 지번 주소나 지적도로 확정 필요`, c);
  }
  return res(null, "invalid", "STD-PNU-01", `${s.length}자리`);
}
