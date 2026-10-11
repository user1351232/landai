"""프로젝트 경로, 지역 설정, 매니페스트, 환경변수 읽기."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_region(region_id: str) -> dict:
    path = ROOT / "config" / "regions" / f"{region_id}.yaml"
    if not path.exists():
        available = sorted(p.stem for p in (ROOT / "config" / "regions").glob("*.yaml"))
        raise SystemExit(f"지역 설정이 없습니다: {region_id} (사용 가능: {', '.join(available)})")
    return load_yaml(path)


def load_manifest(dataset_id: str) -> dict:
    path = ROOT / "manifests" / f"{dataset_id}.yaml"
    if not path.exists():
        available = sorted(p.stem for p in (ROOT / "manifests").glob("*.yaml"))
        raise SystemExit(f"매니페스트가 없습니다: {dataset_id} (사용 가능: {', '.join(available)})")
    return load_yaml(path)


def load_env() -> None:
    """프로젝트 폴더의 .env 를 환경변수로 읽어 옵니다."""
    try:
        from dotenv import load_dotenv
    except ImportError:  # python-dotenv 가 없어도 환경변수로 직접 넣으면 동작
        return
    load_dotenv(ROOT / ".env")


def get_key(name: str) -> str | None:
    """키 읽는 순서: .env / 환경변수 → Streamlit Cloud 비밀값(secrets)."""
    load_env()
    value = os.getenv(name, "").strip()
    if value:
        return value
    try:  # 웹에 배포했을 때는 Streamlit secrets 에 키를 넣습니다
        import streamlit as st
        value = str(st.secrets.get(name, "")).strip()
    except Exception:
        value = ""
    return value or None
