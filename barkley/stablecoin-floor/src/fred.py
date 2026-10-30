"""FRED 데이터를 API 키 없이 CSV로 받고 읽는 함수 (01번 노트북의 함수와 같은 방식)."""
from pathlib import Path

import pandas as pd
import requests

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "fred"


def download_fred(series_id, start=None, refresh=False, raw_dir=RAW_DIR):
    """FRED에서 시리즈 하나를 CSV로 받아 원본 그대로 저장한다. 이미 있으면 refresh=True일 때만 다시 받는다."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{series_id}.csv"
    if path.exists() and not refresh:
        print(f"{series_id:10s} 이미 받은 파일이 있어 건너뜀")
        return path

    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    if start:
        url += f"&cosd={start}"
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    path.write_bytes(response.content)   # 받은 내용을 그대로 저장
    print(f"{series_id:10s} 저장 완료 → {path.name}")
    return path


def read_fred(series_id, raw_dir=RAW_DIR):
    """저장된 원본 CSV를 읽어 '날짜 → 값' Series로 돌려준다. ('.'·빈 칸 → NaN)"""
    df = pd.read_csv(raw_dir / f"{series_id}.csv", dtype=str, index_col=0)
    df.index = pd.to_datetime(df.index)
    return pd.to_numeric(df[series_id], errors="coerce")
