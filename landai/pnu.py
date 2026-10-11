"""필지고유번호(PNU) 표준화.

19자리 = 법정동코드 10 + 산구분 1 (1 일반, 2 산) + 본번 4 + 부번 4

규칙
- STD-PNU-01  19자리 형식 검사
- STD-PNU-02  18자리 손상 복구 (산구분 누락, 본번·부번 앞자리 0 누락)
- STD-PNU-03  엑셀 지수 표기(5.21E+18 등)로 자릿수가 사라진 값 검출 (복구 불가)
- STD-SIDO-01 전북특별자치도 출범 전 시도코드(45) → 현재 코드(52) 변환
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

SCI_RE = re.compile(r"^\s*\d(\.\d+)?[eE]\+?\d+\s*$")
JIBUN_RE = re.compile(r"(산)?\s*(\d+)(?:\s*-\s*(\d+))?")


@dataclass
class PnuResult:
    raw: str
    pnu: str | None          # 표준 19자리 (확정 못 하면 None)
    status: str              # ok | recoded | restored | ambiguous | invalid | sci_notation | empty
    rule: str | None = None
    note: str = ""
    candidates: list[str] = field(default_factory=list)


def clean(raw) -> str:
    """숫자 이외 문자를 지우고, '123.0' 같은 실수 표기를 정리합니다."""
    if raw is None:
        return ""
    s = str(raw).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return re.sub(r"\D", "", s)


def is_valid19(pnu: str) -> bool:
    return (
        len(pnu) == 19
        and pnu.isdigit()
        and pnu[10] in "12"
        and pnu[11:15] != "0000"   # 본번 0000 은 존재하지 않음
    )


def parse_jibun(text: str | None) -> tuple[str, str, str] | None:
    """'산 12-3' → ('2', '0012', '0003'). 지번을 못 찾으면 None."""
    if not text:
        return None
    # '효자동1가 12-3' 처럼 동 이름에도 숫자가 있으므로 마지막 숫자 묶음을 지번으로 봅니다.
    matches = list(JIBUN_RE.finditer(str(text)))
    if not matches:
        return None
    m = matches[-1]
    sangu = "2" if m.group(1) else "1"
    return sangu, m.group(2).zfill(4)[-4:], (m.group(3) or "0").zfill(4)[-4:]


def build(dong10: str, sangu: str, bonbun: int | str, bubun: int | str = 0) -> str:
    return f"{dong10}{sangu}{int(bonbun):04d}{int(bubun):04d}"


def recode_sido(pnu: str, legacy: str | None, current: str | None) -> tuple[str, bool]:
    """시도코드가 옛 코드(45)면 현재 코드(52)로 바꿉니다."""
    if legacy and current and pnu.startswith(legacy):
        return current + pnu[len(legacy):], True
    return pnu, False


def _candidates18(s: str) -> list[str]:
    """18자리 값에서 한 자리를 끼워 넣어 만들 수 있는 19자리 후보."""
    cands = [
        s[:10] + "1" + s[10:],      # 산구분 누락 (일반)
        s[:10] + "2" + s[10:],      # 산구분 누락 (산)
        s[:11] + "0" + s[11:],      # 본번 앞자리 0 누락
        s[:15] + "0" + s[15:],      # 부번 앞자리 0 누락
    ]
    seen, out = set(), []
    for c in cands:
        if c not in seen and is_valid19(c):
            seen.add(c)
            out.append(c)
    return out


def standardize(
    raw,
    *,
    legacy_sido: str | None = None,
    current_sido: str | None = None,
    known_pnus: set[str] | None = None,
    dong_codes: set[str] | None = None,
    jibun_text: str | None = None,
) -> PnuResult:
    """한 값을 19자리 PNU로 표준화합니다.

    known_pnus  연속지적도의 PNU 집합. 있으면 복구 후보를 실제 필지와 대조합니다.
    dong_codes  법정동코드(10자리) 집합. 있으면 후보의 동 코드를 검사합니다.
    jibun_text  같은 행의 지번 주소. 있으면 산구분·본번·부번을 대조합니다.
    """
    raw_s = "" if raw is None else str(raw)
    if not raw_s.strip() or raw_s.strip().lower() == "nan":
        return PnuResult(raw_s, None, "empty")
    if SCI_RE.match(raw_s):
        return PnuResult(raw_s, None, "sci_notation", "STD-PNU-03",
                         "엑셀 지수 표기로 뒷자리가 사라짐. 원본 파일에서 텍스트로 다시 받아야 함")

    s = clean(raw_s)
    jb = parse_jibun(jibun_text)

    def recode(p: str) -> tuple[str, bool]:
        return recode_sido(p, legacy_sido, current_sido)

    def plausible(p: str) -> bool:
        if dong_codes is not None and p[:10] not in dong_codes:
            return False
        if jb is not None and (p[10], p[11:15], p[15:19]) != jb:
            return False
        return True

    if len(s) == 19:
        p, changed = recode(s)
        if not is_valid19(p):
            return PnuResult(raw_s, None, "invalid", "STD-PNU-01", "19자리지만 산구분·본번 형식 오류")
        if changed:
            return PnuResult(raw_s, p, "recoded", "STD-SIDO-01",
                             f"시도코드 {legacy_sido}→{current_sido}")
        return PnuResult(raw_s, p, "ok", "STD-PNU-01")

    if len(s) == 18:
        cands = [recode(c)[0] for c in _candidates18(s)]
        cands = [c for c in dict.fromkeys(cands) if plausible(c)]
        if known_pnus is not None:
            hits = [c for c in cands if c in known_pnus]
            if hits:
                cands = hits
        if len(cands) == 1:
            return PnuResult(raw_s, cands[0], "restored", "STD-PNU-02",
                             "18자리 손상 복구", candidates=cands)
        if not cands:
            return PnuResult(raw_s, None, "invalid", "STD-PNU-02", "복구 후보 없음")
        return PnuResult(raw_s, None, "ambiguous", "STD-PNU-02",
                         f"복구 후보 {len(cands)}개, 지번 주소나 지적도로 확정 필요",
                         candidates=cands)

    return PnuResult(raw_s, None, "invalid", "STD-PNU-01", f"{len(s)}자리")
