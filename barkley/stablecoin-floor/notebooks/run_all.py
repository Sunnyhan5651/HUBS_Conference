"""
7개 노트북을 순서대로 실행한다.

실행:
    python run_all.py           # 전체 실행
    python run_all.py 3         # 3번부터 끝까지
    python run_all.py 2 5       # 2번~5번만

결과:
    각 노트북이 실행된 결과(출력·그래프)가 노트북 파일 안에 저장된다.
    data/processed/ 파일들이 순서대로 생성된다.
"""

import subprocess
import sys
import time
from pathlib import Path

NOTEBOOKS = [
    "01_data_collection.ipynb",
    "02_supply_regression.ipynb",
    "03_rate_model.ipynb",
    "04_floor_pricing.ipynb",
    "05_simulation.ipynb",
    "06_robustness.ipynb",
    "07_final_figures.ipynb",
]

NB_DIR = Path(__file__).parent / "notebooks"
TIMEOUT = 1800  # 최대 30분 / 노트북


def run_notebook(path: Path) -> bool:
    result = subprocess.run(
        [
            sys.executable, "-m", "jupyter", "nbconvert",
            "--to", "notebook",
            "--execute",
            "--inplace",
            f"--ExecutePreprocessor.timeout={TIMEOUT}",
            str(path),
        ]
    )
    return result.returncode == 0


def main():
    args = sys.argv[1:]

    # 실행 범위 파싱
    if len(args) == 0:
        start, end = 1, len(NOTEBOOKS)
    elif len(args) == 1:
        start, end = int(args[0]), len(NOTEBOOKS)
    else:
        start, end = int(args[0]), int(args[1])

    targets = [nb for nb in NOTEBOOKS if int(nb[:2]) >= start and int(nb[:2]) <= end]

    if not targets:
        print("실행할 노트북 없음. 번호를 확인하세요.")
        sys.exit(1)

    print(f"실행 대상: {len(targets)}개 노트북 ({targets[0][:2]} ~ {targets[-1][:2]})\n")

    failed = []
    total_start = time.time()

    for nb in targets:
        path = NB_DIR / nb
        if not path.exists():
            print(f"[건너뜀] {nb} 파일 없음\n")
            continue

        print(f"{'='*55}")
        print(f"▶  {nb}")
        print(f"{'='*55}")
        t0 = time.time()

        ok = run_notebook(path)
        elapsed = time.time() - t0

        if ok:
            print(f"✓  완료  ({elapsed:.0f}초)\n")
        else:
            print(f"✗  실패  ({elapsed:.0f}초)\n")
            failed.append(nb)

    total_elapsed = time.time() - total_start
    print(f"{'='*55}")
    print(f"총 소요 시간: {total_elapsed:.0f}초")

    if failed:
        print(f"\n실패한 노트북 ({len(failed)}개):")
        for nb in failed:
            print(f"  - {nb}")
        sys.exit(1)
    else:
        print("모든 노트북 실행 완료.")


if __name__ == "__main__":
    main()
