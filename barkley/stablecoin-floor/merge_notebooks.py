"""
7개 노트북을 main_analysis.ipynb 하나로 합친다.

실행:
    python merge_notebooks.py

결과:
    stablecoin-floor/main_analysis.ipynb  (보기·수정용 통합 노트북)
"""

import sys
from pathlib import Path

try:
    import nbformat
except ImportError:
    print("nbformat 없음. 설치 중...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "nbformat"], check=True)
    import nbformat

NOTEBOOKS = [
    ("01_data_collection.ipynb",    "1단계: 데이터 수집"),
    ("02_supply_regression.ipynb",  "2단계: 발행량 ~ 금리 회귀분석"),
    ("03_rate_model.ipynb",         "3단계: 금리 모형 (Vasicek)"),
    ("04_floor_pricing.ipynb",      "4단계: 플로어 가격 산출 (바슐리에)"),
    ("05_simulation.ipynb",         "5단계: 몬테카를로 시뮬레이션 + 최적 정책"),
    ("06_robustness.ipynb",         "6단계: 강건성 검증"),
    ("07_final_figures.ipynb",      "7단계: 발제안용 최종 그래프"),
]

ROOT = Path(__file__).parent
NB_DIR = ROOT / "notebooks"
OUT_PATH = ROOT / "main_analysis.ipynb"


def make_divider(title: str, filename: str) -> nbformat.NotebookNode:
    src = (
        f"---\n\n"
        f"# {title}\n\n"
        f"*원본 파일: `notebooks/{filename}`*"
    )
    return nbformat.v4.new_markdown_cell(src)


def merge():
    merged = nbformat.v4.new_notebook()

    # 표지 셀
    cover = nbformat.v4.new_markdown_cell(
        "# 스테이블코인 발행사의 금리 플로어 운용 최적화\n\n"
        "> 「디지털 자산의 제도화와 국내 기업의 대응 전략」 금융공학 파트  \n"
        "> 이 파일은 `merge_notebooks.py`로 자동 생성된 통합 노트북입니다.  \n"
        "> 원본 노트북은 `notebooks/01~07` 폴더에 있습니다.\n\n"
        "**실행 순서**: 01 → 02 → 03 → 04 → 05 → 06 → 07 (앞 단계 결과물을 뒤 단계가 사용합니다)"
    )
    merged.cells.append(cover)

    first_nb = None
    total = 0

    for filename, title in NOTEBOOKS:
        path = NB_DIR / filename
        if not path.exists():
            print(f"  [건너뜀] {filename} 없음")
            continue

        nb = nbformat.read(str(path), as_version=4)

        if first_nb is None:
            first_nb = nb

        merged.cells.append(make_divider(title, filename))
        merged.cells.extend(nb.cells)
        total += len(nb.cells)
        print(f"  병합: {filename}  ({len(nb.cells)}셀)")

    if first_nb is not None:
        merged.metadata = first_nb.metadata

    nbformat.write(merged, str(OUT_PATH))
    print(f"\n완료: {OUT_PATH}")
    print(f"총 {len(merged.cells)}셀 ({total}셀 + 구분 셀 {len(merged.cells) - total}개)")


if __name__ == "__main__":
    merge()
