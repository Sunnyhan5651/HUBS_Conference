# USD/KRW 이벤트 드리븐 백테스트

**디지털 자산 제도화 이벤트가 원/달러 환율에 미치는 영향 분석**

---

## 연구 배경

barkley 팀의 분석 결과, 디지털 자산 제도화 이벤트가 미국 국채 금리에는 통계적으로 유의한 영향을 주지 않는 것으로 나타났다 (`barkley/README.md`). 이에 본 분석은 **"미국 금리보다 USD/KRW 환율 채널을 통한 국내 전이 가능성"** 을 검증한다.

가설: 긍정적 제도화 이벤트 → 위험선호 심리 → 원화 강세(DEXKOUS 하락) → 방향 조정 AR > 0

---

## 데이터

| 변수 | 출처 | 식별자 |
|------|------|--------|
| USD/KRW 일별 환율 | FRED | `DEXKOUS` (fredapi) |
| BOK 기준금리 | ECOS (한국은행) | `722Y001 / 0001000` |
| 이벤트 목록 | `sunkyu/data/이벤트 리스트 제안.xlsx` | Sheet: 이벤트 리스트 |

- API 키: `sunkyu/config.py` (gitignore 처리, 미공개)
- 표본 기간: 2015-01-01 ~
- Main 표본: 22건 (M01–M22), 이벤트 t0 = **한국 주식 t0**

---

## 방법론

### 이벤트 스터디 (Event Study)

```
추정 창: [t0 − 126, t0 − 6]  → 120 거래일
이벤트 창: [-5, +5] (메인) / [-1, +1] (보조)
정상 수익률: 추정 창 평균 수익률 (Constant Mean Return Model)
AR(t) = r(t) − μ_est
```

> USD/KRW는 주가처럼 단일 팩터에 명확히 귀속되지 않아 시장 모형보다 단순 평균 모형이 일반적으로 선호됨

### 방향 조정

이벤트 방향 `+1`(긍정) / `-1`(부정)을 고려한 가설 검정:

```
Dir-Adj AR = AR × (−direction)
```

긍정 이벤트에서 원화 강세(DEXKOUS↓, AR < 0)라면 Dir-Adj AR > 0 → 가설 지지

### 통계 검정

| 검정 | 설명 |
|------|------|
| **BMP 검정** | Standardized AR (sAR = AR / σ_est) 기반, 분산 이분산 강건 |
| **부호 검정** | 양수 AR 비율의 이항검정 (H₀: 50%) |
| **Placebo 검정** | 2,000회 무작위 날짜 추출 → 실제 CAAR 백분위수 산출 |

### 오염 판정 (±2 거래일)

- **FOMC / CPI**: xlsx `매크로 일정 겹침` 컬럼 파싱
- **BOK 기준금리 변경**: ECOS 422Y001 diff > 0.01%p 탐지
- 오염 이벤트 포함한 **전체 표본** vs 제외한 **clean 표본** 비교

---

## 출력 결과

| 파일 | 내용 |
|------|------|
| `output/01_caar_comparison.png` | 두 이벤트 창 CAAR (전체 / 방향 조정) |
| `output/02_aar_by_day.png` | 일별 AAR 막대 (유의 구간 빨강) |
| `output/03_caar_pos_neg.png` | 긍정 vs 부정 이벤트 CAAR |
| `output/04_full_vs_clean.png` | 전체 vs 오염 제외 비교 |
| `output/05_placebo.png` | Placebo 검정 분포 |
| `output/results_all.csv` | 전 이벤트 창 BMP / 부호검정 결과 |
| `output/results_clean_compare.csv` | 전체 vs 오염 제외 t=0 비교 |
| `output/bok_rate_changes.csv` | BOK 금리 변경 이력 |

---

## 실행 방법

```bash
cd sunkyu/USD_KRW_backtest
python USD_KRW_backtest.py
```

**사전 준비:**
1. `sunkyu/config.py`에 API 키 입력 (FRED, ECOS)
2. 패키지 설치: `pip install fredapi pandas numpy matplotlib scipy openpyxl`

---

## 해석 가이드

| 결과 패턴 | 해석 |
|-----------|------|
| 전체·clean 모두 유의하지 않음 | 크립토 충격이 환율 채널로 전이되지 않음 |
| 전체는 유의, clean은 유의하지 않음 | 매크로 이슈(FOMC 등)가 결과를 왜곡 → 제도화 효과 아님 |
| 전체·clean 모두 유의 | 환율 채널을 통한 전이 존재 |
| 방향 조정 AR 양수 + 유의 | 긍정 이벤트 → 원화 강세 가설 지지 |

---

## 관련 파일

- `sunkyu/bond_backtest/` — 미국 국채 금리 이벤트 스터디 (barkley 팀 결과와 비교)
- `barkley/README.md` — 미국 금리 무반응 분석 결과
- `sunkyu/data/이벤트 리스트 제안.xlsx` — 이벤트 원본 데이터
