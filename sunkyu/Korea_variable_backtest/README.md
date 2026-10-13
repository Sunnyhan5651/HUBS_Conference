# 국내 변수 이벤트 드리븐 백테스트

**디지털 자산 제도화 이벤트가 KOSPI · KOSDAQ · 국고채 수익률에 미치는 영향 분석**

---

## 연구 배경

barkley 팀(미국 국채 금리)과 sunkyu USD/KRW 분석에서 모두 유의한 반응이 없었다. 본 분석은 동일 이벤트가 **국내 자산 시장**에도 전이되지 않는지를 검증한다.

```
[barkley]  제도화 이벤트 → 미국 국채 금리 반응?   → 없음
[sunkyu1]  제도화 이벤트 → USD/KRW 반응?          → 없음
[sunkyu2]  제도화 이벤트 → KOSPI·KOSDAQ·국고채 반응? → 본 파일
```

---

## 데이터

| 변수 | 출처 | 식별자 |
|------|------|--------|
| KOSPI | FinanceDataReader (KRX) | `KS11` |
| KOSDAQ | FinanceDataReader (KRX) | `KQ11` |
| 국고채 3년 수익률 | ECOS API | `817Y002 / 010200000` (Cycle: D) |
| 국고채 10년 수익률 | ECOS API | `817Y002 / 010210000` (Cycle: D) |
| 이벤트 목록 | `sunkyu/data/이벤트 리스트 제안.xlsx` | Sheet: 이벤트 리스트 |

- API 키: `sunkyu/config.py` (gitignore 처리, 미공개)
- 표본 기간: 2015-01-01 ~
- Main 표본: 22건 (M01–M22), 이벤트 t0 = **한국 주식 t0**

---

## 방법론

### 이벤트 스터디

```
추정 창: [t0 − 126, t0 − 6]  → 120 거래일
이벤트 창: [-5, +5] (메인) / [-1, +1] (보조)
정상 수익률: Constant Mean Return Model
AR(t) = actual_change(t) − μ_est
```

**단위 구분**
- KOSPI / KOSDAQ: 일수익률 `pct_change() × 100` (%)
- 국고채 3·10년: 일수익률변화 `diff() × 100` (bp)

### 방향 조정 (KOSPI·KOSDAQ만)

```
Dir-Adj AR = AR × direction
```

긍정 이벤트에서 주가 상승 → Dir-Adj AR > 0 이면 가설 지지.  
국고채 수익률의 방향은 불명확하여 방향 조정 생략.

### 통계 검정

| 검정 | 설명 |
|------|------|
| **BMP 검정** | Standardized AR (sAR = AR / σ_est) 기반 |
| **부호 검정** | 양수 AR 비율의 이항검정 (H₀: 50%) |
| **Placebo 검정** | 2,000회 무작위 날짜 → 실제 CAAR 백분위수 |

### 오염 판정 (±2 거래일)

FOMC / CPI가 이벤트 창 ±2 거래일 이내 → 오염 이벤트로 분류.  
전체 표본(22건) vs clean 표본(약 9건) 비교.

---

## 출력 결과

| 파일 | 내용 |
|------|------|
| `output/01_caar_4variables.png` | 4개 변수 CAAR 2×2 그리드 ([-5,+5]) |
| `output/02_t0_bar_comparison.png` | t=0 AAR 4변수 막대 비교 |
| `output/03_caar_pos_neg_equity.png` | KOSPI·KOSDAQ 긍정 vs 부정 이벤트 |
| `output/04_full_vs_clean.png` | 전체 vs 오염 제외 비교 |
| `output/05_placebo_kospi.png` | KOSPI Placebo 분포 |
| `output/results_all.csv` | 전 변수·전 이벤트 창 BMP / 부호검정 |
| `output/results_t0_summary.csv` | t=0 요약 (전체 / clean 비교) |

---

## 실행 방법

```bash
cd sunkyu/Korea_variable_backtest
python Korea_variable_backtest.py
```

**사전 준비:**
1. `sunkyu/config.py`에 ECOS API 키 입력
2. 패키지 설치: `pip install finance-datareader pandas numpy matplotlib scipy openpyxl`

---

## 분석 결과 (Main 22건, 2015–2026)

### 핵심 결론

> **이벤트 당일(t=0)**: KOSPI·KOSDAQ·국고채 모두 통계적으로 유의하지 않음 (p > 0.22)

> **국고채 3년 Placebo p=0.031 (★)**: 이벤트 창 전체([-5,+5]) CAAR +6.19bp가 무작위 분포 대비 유의하나, 이벤트 당일 자체는 p=0.22로 무유의 → "창 내 어딘가에 누적 효과"이지 당일 충격은 아님

### t=0 이벤트 당일 요약

| 변수 | 단위 | AAR(t=0) | t_BMP | p(전체) | p(clean) |
|------|------|---------|-------|---------|----------|
| KOSPI | % | -0.139 | +0.36 | 0.721 | 0.857 |
| KOSDAQ | % | +0.035 | +0.69 | 0.499 | 0.730 |
| 국고채 3년 | bp | +0.838 | +1.26 | 0.222 | 0.995 |
| 국고채 10년 | bp | +0.294 | +0.54 | 0.596 | 0.543 |

### Placebo 검정

| 변수 | 실제 CAAR | Placebo μ | p |
|------|-----------|-----------|---|
| KOSPI | +1.04% | +0.01% | 0.292 |
| KOSDAQ | +0.21% | -0.08% | 0.799 |
| **국고채 3년** | **+6.19bp** | **+0.11bp** | **0.031 ★** |
| 국고채 10년 | +3.87bp | -0.06bp | 0.187 |

### 주요 발견 해석

**KOSPI / KOSDAQ: 무반응**

이벤트 당일과 clean 표본 모두 p > 0.49. 국내 주식시장은 디지털 자산 제도화 이벤트에 체계적으로 반응하지 않는다.

**국고채 3년 Placebo 유의성 (p=0.031): 신중한 해석 필요**

- 이벤트 창 전체 CAAR +6.19bp는 Placebo 분포 대비 통계적으로 크나, 이벤트 당일(t=0) BMP p=0.22로 충격이 특정 시점에 집중되지 않음
- 유의한 일별 시점: t-4 (p=0.032)와 t+3 (p=0.011) — 사전 예측이나 사후 반응이 아닌 노이즈일 가능성
- 부호검정 p=0.05 이상 (단순 다수결 기준 불충족)
- **해석**: 제도화 이벤트가 국내 채권시장에 미세한 수익률 상승 압력을 주는 경향이 있으나, 통계적 강건성이 낮아 결정적 증거로 보기 어렵다

**전체 연구 내러티브 업데이트**

```
[barkley]   미국 국채 금리 → 무반응
[sunkyu1]   USD/KRW       → 무반응
[sunkyu2]   KOSPI/KOSDAQ  → 무반응
            국고채 3년    → Placebo 경계선 유의 (해석 신중)
```

> **"크립토 제도화 충격은 전통 금융 시장 전반에 전이되지 않는다"** 는 결론이 일관되게 지지됨.  
> 국고채 3년의 경계선 Placebo 결과는 향후 Robust 표본(49건)으로 재검증할 필요가 있다.

---

## 관련 파일

- `sunkyu/USD_KRW_backtest/` — 원/달러 환율 이벤트 스터디
- `sunkyu/bond_backtest/` — 미국 국채 금리 이벤트 스터디
- `barkley/README.md` — 미국 금리 무반응 분석 결과
- `sunkyu/data/이벤트 리스트 제안.xlsx` — 이벤트 원본 데이터
