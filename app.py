"""위치 기반 AI 토지 분석 플랫폼 - 웹 화면 (v0.5)

실행:  streamlit run app.py      (또는 python -m landai web)
"""

from __future__ import annotations

import json

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from landai.apis import vworld
from landai.apis.http import using_proxy
from landai.config import get_key, load_region
from landai.pipeline import analyze

st.set_page_config(page_title="위치 기반 AI 토지 분석", page_icon="🗺️", layout="wide")

REGIONS = {"jeonju": "전주시", "wanju": "완주군"}
DEFAULT_POINT = (127.1480, 35.8242)          # 전주시청 부근 (경도, 위도)
GRADE_COLOR = {"확정": "#1a7f37", "복원": "#1f6feb", "추정": "#d4a72c", "미연결": "#cf222e"}

ss = st.session_state
ss.setdefault("point", None)                 # (lon, lat)
ss.setdefault("last_click", None)
ss.setdefault("choice", None)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_parcels(lon: float, lat: float):
    return vworld.parcels_at(lon, lat)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_geocode(address: str):
    return vworld.geocode(address)


def set_point(lon: float, lat: float) -> None:
    ss.point = (round(lon, 6), round(lat, 6))
    ss.choice = None


# ---------------- 사이드바: 입력 ----------------
with st.sidebar:
    st.header("위치 입력")
    region_id = st.selectbox("대상 지역", list(REGIONS), format_func=REGIONS.get)
    region = load_region(region_id)

    mode = st.radio("입력 방식", ["위경도", "주소", "지도 클릭"], horizontal=True)
    if mode == "위경도":
        lat = st.number_input("위도", value=DEFAULT_POINT[1], format="%.6f", step=0.0001)
        lon = st.number_input("경도", value=DEFAULT_POINT[0], format="%.6f", step=0.0001)
        if st.button("분석하기", type="primary"):
            set_point(lon, lat)
    elif mode == "주소":
        address = st.text_input("주소", placeholder="예: 전주시 완산구 노송광장로 10")
        if st.button("분석하기", type="primary") and address:
            try:
                g = cached_geocode(address)
                if g:
                    set_point(g["lon"], g["lat"])
                    st.caption(f"{g['type']} 주소로 찾음: {g['address']}")
                else:
                    st.warning("주소를 찾지 못했습니다. 시·구 이름부터 적어 보세요.")
            except vworld.VworldError as e:
                st.error(str(e))
    else:
        st.info("오른쪽 지도에서 분석할 곳을 클릭하세요.")

    st.divider()
    base = st.radio("배경지도", ["브이월드 위성", "브이월드 일반", "OpenStreetMap"])
    st.caption("지도가 회색으로 나오면 OpenStreetMap 으로 바꿔 보세요.")
    st.caption("API 호출 경로: " + ("서울 중계 서버" if using_proxy() else "직접 호출"))

# ---------------- 분석 ----------------
result = None
if ss.point:
    with st.spinner("분석 중..."):
        result = analyze(ss.point[0], ss.point[1], region, choice=ss.choice,
                         fetch=cached_parcels)

# ---------------- 본문 ----------------
st.title("위치 기반 AI 토지 분석")
st.caption("위치를 입력하면 필지를 찾아 검사하고, 단계마다 분석 이력을 남깁니다.")

col_map, col_info = st.columns([3, 2], gap="large")

with col_map:
    center = (ss.point[1], ss.point[0]) if ss.point else (DEFAULT_POINT[1], DEFAULT_POINT[0])
    m = folium.Map(location=center, zoom_start=18 if ss.point else 13, tiles=None,
                   control_scale=True)
    key = get_key("VWORLD_KEY")
    if base.startswith("브이월드") and key:
        layer = "Satellite" if base == "브이월드 위성" else "Base"
        folium.TileLayer(vworld.tile_url(key, layer), attr="© VWorld", max_zoom=19,
                         name=base).add_to(m)
        if layer == "Satellite":
            folium.TileLayer(vworld.tile_url(key, "Hybrid"), attr="© VWorld", max_zoom=19,
                             overlay=True, name="지명").add_to(m)
    else:
        folium.TileLayer("OpenStreetMap", max_zoom=19).add_to(m)

    if result and result["parcels"]:
        for i, f in enumerate(result["parcels"]):
            chosen = result["parcel"] is f
            color = GRADE_COLOR.get(result["grade"], "#888") if chosen else "#888"
            folium.GeoJson(
                f, style_function=lambda _x, c=color, ch=chosen: {
                    "color": c, "weight": 3 if ch else 1.5, "fillOpacity": 0.25 if ch else 0.05,
                    "dashArray": None if ch else "5 5"},
                tooltip=f.get("properties", {}).get("addr", f"후보 {i + 1}"),
            ).add_to(m)
    if ss.point:
        folium.Marker((ss.point[1], ss.point[0]), tooltip="입력 위치").add_to(m)

    out = st_folium(m, height=620, use_container_width=True, key="map",
                    returned_objects=["last_clicked"])
    click = (out or {}).get("last_clicked")
    if click and click != ss.last_click:
        ss.last_click = click            # 다른 입력 방식일 때 찍힌 클릭은 기록만 해 둠
        if mode == "지도 클릭":
            set_point(click["lng"], click["lat"])
            st.rerun()

with col_info:
    if not result:
        st.info("왼쪽에서 위치를 입력하고 '분석하기'를 누르세요.")
    else:
        status = result["status"]
        if status == "outside":
            st.error(f"{region['name']} 범위 밖입니다. 지원 지역을 바꾸거나 위치를 다시 입력하세요.")
        elif status == "error":
            st.error(result["log"][-1]["결과"])
        elif status == "no_parcel":
            st.warning("이 위치에서 필지를 찾지 못했습니다. 도로나 하천 위일 수 있어요.")
        elif status == "multiple":
            st.warning("후보 필지가 여러 개입니다. 분석할 필지를 고르세요.")
            labels = [f.get("properties", {}).get("addr", f"후보 {i + 1}")
                      for i, f in enumerate(result["parcels"])]
            pick = st.radio("후보 필지", range(len(labels)), format_func=labels.__getitem__)
            if st.button("이 필지로 분석"):
                ss.choice = pick
                st.rerun()
        else:
            props = result["parcel"].get("properties", {})
            grade = result["grade"]
            st.markdown(
                f"<span style='background:{GRADE_COLOR[grade]};color:white;padding:4px 10px;"
                f"border-radius:12px;font-weight:600'>연결 확신도: {grade}</span>",
                unsafe_allow_html=True)
            st.subheader(props.get("addr", "필지"))
            c1, c2 = st.columns(2)
            c1.metric("면적 (EPSG:5186)",
                      f"{result['area_m2']:,} ㎡" if result["area_m2"] is not None else "계산 안 됨")
            try:
                jiga_text = f"{int(float(props.get('jiga'))):,} 원/㎡"
            except (TypeError, ValueError):
                jiga_text = "정보 없음"
            c2.metric("개별공시지가", jiga_text)
            st.code(result["pnu"]["pnu"] or result["pnu"]["raw"], language=None)

            rows = [(vworld.PARCEL_LABELS.get(k, k), v) for k, v in props.items()]
            st.dataframe(pd.DataFrame(rows, columns=["항목", "값"]), hide_index=True)

        st.markdown("#### 분석 이력서")
        st.dataframe(pd.DataFrame(result["log"]), hide_index=True)
        report = {k: v for k, v in result.items() if k not in ("parcels",)}
        st.download_button("분석 이력서 내려받기 (JSON)",
                           json.dumps(report, ensure_ascii=False, indent=2, default=str),
                           file_name="analysis_report.json", mime="application/json")
