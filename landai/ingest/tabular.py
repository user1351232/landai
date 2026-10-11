"""표 자료(CSV·엑셀) 수신 검사.

- INGEST-ROW-01  열 개수가 맞지 않는 깨진 줄 격리 (13줄 사례)
- INGEST-COL-01  기대 컬럼 누락
- INGEST-PNU-01  필지번호 형식·손상 검사 (18자리 사례, 엑셀 지수 표기)
- DATA-01        자료 공백 연도
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from landai import pnu as pnu_mod
from landai.profile import DataProfile

ENCODINGS = ("utf-8-sig", "cp949", "euc-kr")
PNU_NAME_RE = re.compile(r"(^pnu$|필지고유번호|고유번호|pnu)", re.I)
YEAR_NAME_RE = re.compile(r"(허가일|허가일자|허가년|일자|연도|년도|date|year)", re.I)
CODE_NAME_RE = re.compile(r"(법정동코드|법정동_코드|bjd|code)", re.I)


@dataclass
class TableRead:
    df: pd.DataFrame
    encoding: str
    delimiter: str
    quarantine: list[dict]       # 깨진 줄 [{line, fields, raw}]
    header: list[str]


def detect_encoding(path: Path) -> str:
    data = path.read_bytes()[:200_000]
    for enc in ENCODINGS:
        try:
            data.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "cp949"


def read_table(path: Path) -> TableRead:
    """CSV·TXT는 줄 단위로 읽어 깨진 줄을 따로 모읍니다. 엑셀은 그대로 읽습니다.
    모든 값은 문자열로 읽어 필지번호 앞자리 0이 사라지지 않게 합니다."""
    if path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(path, dtype=str)
        return TableRead(df, "excel", "", [], list(df.columns))

    enc = detect_encoding(path)
    text = path.read_text(encoding=enc, errors="replace")
    sample = text[:20_000]
    try:
        delim = csv.Sniffer().sniff(sample, delimiters=",\t|;").delimiter
    except csv.Error:
        delim = ","

    reader = csv.reader(io.StringIO(text), delimiter=delim)
    rows, quarantine = [], []
    header: list[str] | None = None
    for i, fields in enumerate(reader, start=1):
        if not fields or all(not f.strip() for f in fields):
            continue
        if header is None:
            header = [h.strip() for h in fields]
            continue
        if len(fields) != len(header):
            quarantine.append({"line": i, "fields": len(fields),
                               "raw": delim.join(fields)})
            continue
        rows.append(fields)
    header = header or []
    df = pd.DataFrame(rows, columns=header, dtype=str)
    return TableRead(df, enc, delim, quarantine, header)


def find_column(columns, setting, pattern: re.Pattern) -> str | None:
    if setting in (None, "", False):
        return None
    if setting != "auto":
        return setting if setting in columns else None
    for c in columns:
        if pattern.search(str(c)):
            return c
    return None


def extract_years(series: pd.Series) -> pd.Series:
    """'2021-03-05', '20210305', '2021' 등에서 연도를 뽑습니다."""
    s = series.dropna().astype(str).str.extract(r"((?:19|20)\d{2})")[0]
    return pd.to_numeric(s, errors="coerce").dropna().astype(int)


def check_table(path: Path, manifest: dict, region: dict, profile: DataProfile,
                quarantine_dir: Path, known_pnus: set[str] | None = None,
                dong_codes: set[str] | None = None) -> TableRead:
    t = read_table(path)
    profile.stats.update(rows=len(t.df), columns=t.header, encoding=t.encoding,
                         delimiter=t.delimiter)

    # INGEST-ROW-01
    if t.quarantine:
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        qpath = quarantine_dir / f"{profile.region}_{profile.dataset}_broken_rows.csv"
        pd.DataFrame(t.quarantine).to_csv(qpath, index=False, encoding="utf-8-sig")
        profile.add("INGEST-ROW-01", "warn",
                    f"깨진 줄 {len(t.quarantine)}줄 격리 (열 개수 불일치)",
                    count=len(t.quarantine), file=str(qpath),
                    lines=[q["line"] for q in t.quarantine[:50]])
    else:
        profile.add("INGEST-ROW-01", "pass", "깨진 줄 없음")

    # INGEST-COL-01
    expected = manifest.get("expected_columns") or []
    if expected:
        missing = [c for c in expected if c not in t.header]
        if missing:
            profile.add("INGEST-COL-01", "fail", f"기대 컬럼 누락: {', '.join(missing)}",
                        missing=missing, actual=t.header)
        else:
            profile.add("INGEST-COL-01", "pass", "기대 컬럼 모두 있음")
    else:
        profile.add("INGEST-COL-01", "warn",
                    "매니페스트에 기대 컬럼이 비어 있음. 실제 컬럼을 확인해 채우세요",
                    actual=t.header)

    # INGEST-PNU-01
    pnu_col = find_column(t.header, manifest.get("pnu_column"), PNU_NAME_RE)
    if manifest.get("pnu_column") and not pnu_col:
        profile.add("INGEST-PNU-01", "warn", "필지번호 컬럼을 찾지 못함", columns=t.header)
    elif pnu_col:
        check_pnu_series(t.df[pnu_col], region, profile, quarantine_dir,
                         known_pnus=known_pnus, dong_codes=dong_codes)

    # DATA-01
    year_col = find_column(t.header, manifest.get("year_column"), YEAR_NAME_RE)
    if year_col:
        check_year_gaps(t.df[year_col], manifest.get("expected_years"), profile, year_col)

    return t


def check_pnu_series(series: pd.Series, region: dict, profile: DataProfile,
                     quarantine_dir: Path, known_pnus=None, dong_codes=None) -> pd.DataFrame:
    results = [
        pnu_mod.standardize(v, legacy_sido=region.get("legacy_sido_code"),
                            current_sido=region.get("sido_code"),
                            known_pnus=known_pnus, dong_codes=dong_codes)
        for v in series.tolist()
    ]
    df = pd.DataFrame([{"row": i, "raw": r.raw, "pnu": r.pnu, "status": r.status,
                        "note": r.note, "candidates": "|".join(r.candidates)}
                       for i, r in enumerate(results)])
    counts = df["status"].value_counts().to_dict()
    bad = df[df["status"].isin(["invalid", "ambiguous", "sci_notation"])]
    if len(bad):
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        qpath = quarantine_dir / f"{profile.region}_{profile.dataset}_pnu_issues.csv"
        bad.to_csv(qpath, index=False, encoding="utf-8-sig")
    else:
        qpath = None
    status = "fail" if counts.get("sci_notation") else ("warn" if len(bad) or
                                                       counts.get("restored") else "pass")
    msg = ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
    profile.add("INGEST-PNU-01", status, f"필지번호 검사: {msg}", counts=counts,
                issues_file=str(qpath) if qpath else None)
    if counts.get("recoded"):
        profile.add("STD-SIDO-01", "warn",
                    f"옛 시도코드 필지번호 {counts['recoded']}건을 현재 코드로 변환 대상",
                    count=counts["recoded"])
    return df


def check_year_gaps(series: pd.Series, expected_years, profile: DataProfile, col: str) -> None:
    years = extract_years(series)
    if years.empty:
        profile.add("DATA-01", "warn", f"'{col}'에서 연도를 읽지 못함")
        return
    lo, hi = (expected_years or [int(years.min()), int(years.max())])
    present = set(years.tolist())
    missing = [y for y in range(lo, hi + 1) if y not in present]
    per_year = years.value_counts().sort_index().to_dict()
    if missing:
        profile.add("DATA-01", "warn", f"자료 공백 연도: {', '.join(map(str, missing))}",
                    missing=missing, per_year=per_year, column=col)
    else:
        profile.add("DATA-01", "pass", f"{lo}~{hi} 연도 모두 있음", per_year=per_year,
                    column=col)
