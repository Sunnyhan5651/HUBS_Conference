# 스테이블코인 발행사의 금리 플로어 운용 최적화

공모전 발제안 「디지털 자산의 제도화와 국내 기업의 대응 전략」의 금융공학 파트. 스테이블코인 발행사가 금리 하락 위험을 금리 플로어로 어떻게 관리해야 하는지 몬테카를로 시뮬레이션으로 분석했다.

**결과물 바로가기**: [보고서](output/report.md) · [한 장 요약](output/one_pager.md) · [예상 질문](output/qna.md) · [한계](output/limitations.md) · [최종 그래프](output/figures/final/)

## 폴더 구조

```
CLAUDE.md          분석 설계와 결정 사항 (최종 범위는 맨 위)
data/raw/          받은 원본 그대로 (FRED, DefiLlama, SEC) — 수정 금지
data/processed/    정리된 데이터, 파라미터, 강건성 판정
notebooks/         분석 노트북 (아래 순서대로 실행)
src/               노트북에서 같이 쓰는 함수
output/            보고서·요약·질문·한계 (md), figures/ (그래프), figures/final/ (발제안용)
```

## 노트북 실행 순서

| 순서 | 노트북 | 하는 일 |
|---|---|---|
| 1 | `01_data_collection` | 금리(FRED), 스테이블코인 유통량(DefiLlama), Circle 재무제표(SEC) 수집·정리 |
| 2 | `02_supply_regression` | 발행량과 금리의 관계 회귀분석, 자연 헤지 크기 |
| 3 | `03_rate_model` | Vasicek 금리 모형 추정과 검증 |
| 4 | `04_floor_pricing` | 수익률곡선 보정, 바슐리에 플로어 가격표 |
| 5 | `05_simulation` | 발행사 3곳 × 전략 25개 몬테카를로, 효율적 투자선, 최적 정책 |
| 6 | `06_robustness` | 시뮬레이션 오차, 파라미터 불확실성, 가정 변경 8개 |
| 7 | `07_final_figures` | 발제안용 최종 그래프 5장 |

- 앞 노트북이 만든 `data/processed/` 파일을 뒤 노트북이 읽으므로 **순서대로** 실행한다.
- 원본 데이터가 이미 있으면 다운로드를 건너뛴다. 최신 데이터로 다시 받으려면 01번의 `REFRESH = True`로 바꾼다(결과 숫자가 바뀐다).

## 실행 방법

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m ipykernel install --user --name stablecoin-floor --display-name "Python (stablecoin-floor)"
```

VS Code나 Jupyter에서 노트북을 열고 커널을 **Python (stablecoin-floor)**로 고른 뒤 "모두 실행". 명령줄로 한꺼번에 실행하려면:

```
cd notebooks
jupyter nbconvert --to notebook --execute --inplace 01_data_collection.ipynb
(02 ~ 07도 같은 방식)
```

## 데이터 출처
- FRED: SOFR, 연방기금 실효금리, 미국채 수익률(1개월~10년), FOMC 장기 전망, 비트코인 가격
- DefiLlama stablecoins API: USDC·USDT·전체 스테이블코인 유통량
- SEC EDGAR XBRL API: Circle(CIK 1876042) 재무제표 (요청 시 User-Agent에 연락처 필요)

데이터 기준일: 2026-10-26
