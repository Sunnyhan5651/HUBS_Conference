# HUBS_Conference

## 연구 주제: 디지털 자산의 제도화에 따른 국내 기업의 대응전략

---

## 연구 프레임워크

```
[최종 목표] 국내 기업의 디지털 자산 대응전략 도출
      │
      ├── [Part 1] 정량 분석 — 이벤트 드리븐 백테스트
      │         미국 제도화 이벤트 → BTC/ETH 가격 충격 실증
      │         크로스에셋·매크로 반응 분석
      │         → 헤징 전략 / ETF 구성 근거 확보
      │
      └── [Part 2] 정성 분석 — 시장 구조 변화 분석
                스테이블코인 제도화 → 기업 결제·재무 운용 전략
                RWA/STO 제도화   → 기업 자산 토큰화 진입 전략
```

**핵심 논리 구조**: Part 1이 "제도화가 시장에 어떤 충격을 주는가"를 실증하고, Part 2가 "그 구조 변화에 국내 기업은 어떻게 포지셔닝해야 하는가"를 제안. 두 파트는 별개가 아니라 정량→정성의 근거 흐름으로 연결됨.

**한-미 벤치마크 전략**: 국내 제도화 사례가 부족하므로 미국 사례를 이벤트 원천으로 활용. 미국 이벤트와 국내 시장 반응의 동조화를 실증하여 국내 적용 가능성을 확보.

---

# Part 1. 정량 분석: 이벤트 드리븐 백테스트

## 1-1. 제도화 이벤트별 가격 충격 카탈로그

### [카테고리 A] 파생상품 시장 진입

| 날짜 | 이벤트 | BTC 가격 충격 | 비고 |
|------|--------|--------------|------|
| 2017-12-10 | CBOE Bitcoin 선물 출시 | +19% (첫날) | 기관 숏 포지션 진입 가능 → 장기 하락 전환점 |
| 2017-12-18 | CME Bitcoin 선물 출시 | -2% (당일) / 사전 +288% | 비관론자 시장 진입 → 1년 이상 하락 시작 |
| 2021-10-19 | ProShares BITO (미국 최초 선물 ETF) | +4.8% (당일), BTC $67,016 신고가 | 출시 이틀 만에 $1B 유입 |

> CME 선물 출시는 사전 +288% 랠리 후 당일 -2% 전환 → 기관 숏 진입이 장기 하락 구조를 만든 전형적인 "기대→실망" 패턴의 원형.

---

### [카테고리 B] 기업 재무 자산 편입 (Corporate Treasury)

| 날짜 | 이벤트 | BTC 가격 충격 | 비고 |
|------|--------|--------------|------|
| 2020-08-11 | MicroStrategy 초기 매수 ($250M, 21,454 BTC) | 당일 -2% / 주간 소폭 플러스 | 기업 재무 편입 첫 사례, MSTR 주가 이후 ~5배 |
| 2020-Q4 | MicroStrategy 전환사채 발행 → BTC 추가매수 ($650M) | 2020년 BTC $10K → $29K (연말) | 기관 모방 수요 촉발 |
| 2021-02-08 | Tesla $1.5B BTC 매수 + 결제 허용 발표 | +~17% 당일, $46,203 도달 | 기업 편입 붐 확산 신호 |

> 공시 당일 단기 하락(-2%) 후 주간 반등 패턴이 반복됨. Tesla는 예외적으로 즉각 급등 → Elon Musk 영향력 변수로 분리 처리 필요.

---

### [카테고리 C] ETF 승인 및 규제 이정표

| 날짜 | 이벤트 | BTC 가격 충격 | 비고 |
|------|--------|--------------|------|
| 2021-02-18 | 캐나다 Purpose Bitcoin ETF 승인 (북미 최초) | 소폭 상승, 초일 거래량 $400M+ | 미국 승인 전 선행 지표 역할 |
| 2021-04-14 | Coinbase NASDAQ 직상장 (COIN IPO) | BTC $64,829 신고가 | 당일 역대 고점 → 이후 차익실현 급락 |
| 2023-06-15 | BlackRock iShares Bitcoin Trust 신청 | 이후 수주간 BTC ~20% 상승 | 세계 최대 자산운용사 진입 → ETF 낙관론 재점화 |
| 2023-08-29 | Grayscale vs SEC 법원 판결 (SEC 패소) | 당일 BTC +7.15%, 시총 +$50B | COIN +13%, MARA +18%, RIOT +24% |
| 2024-01-10 | SEC 비트코인 현물 ETF 11개 동시 승인 | 당일 소폭 (사전 선반영), 이후 3월 $73,000+ | 6개월 전부터 $29K → $48K 선행 상승 |

> 승인 이벤트 대부분 "Buy the Rumor, Sell the News" 패턴. Announcement Date와 Effective Date를 분리한 이중 이벤트 윈도우 설계 필수.

---

### [카테고리 D] 주권 국가 / 정책 이벤트

| 날짜 | 이벤트 | BTC 가격 충격 | 비고 |
|------|--------|--------------|------|
| 2021-09-07 | 엘살바도르 비트코인 법정화폐 지정 | 단기 소폭 상승 후 조정 | 국가 채택 선례, 실질 시장 충격 제한적 |
| 2024-04-19 | BTC 4차 반감기 | 이후 +33% (6개월) | 현물 ETF 기관 수요와 맞물려 이전 사이클보다 충격 완화 |
| 2025-03-06 | 트럼프 전략 비트코인 준비금 행정명령 | 오히려 단기 하락 (시장 실망) | "압수물 한정" 내용이 기대치 하회 |

---

### [카테고리 E] 부정적 이벤트 — 스테이블코인 디페깅 (헤지 관점 핵심)

스테이블코인 디페깅은 정성 분석 파트의 주제이기도 하지만, 직접적인 BTC/ETH 가격 충격 이벤트로서 정량 파트에도 포함.

| 날짜 | 이벤트 | 충격 내용 | 전이 범위 |
|------|--------|----------|---------|
| 2022-05-07~12 | **LUNA/UST 알고리즘 디페깅** | BTC -50% 이상, 시총 $60B 소각 | 3AC, Celsius, Voyager 연쇄 파산 → FTX 붕괴 도화선 |
| 2022-05-12 | **USDT 일시 디페깅** ($0.945) | BTC 동반 하락, USDT $10B 이상 환매 | 24시간 내 $0.998 회복, 단기 패닉성 |
| 2022-11-08~16 | **FTX 파산** | BTC -25%, ETH -30%, 시총 -$260B | COIN 채권 -15%, BlockFi 파산, S&P500은 무영향 |
| 2023-03-10~13 | **USDC/SVB 디페깅** ($0.87) | USDC 기반 DeFi 프로토콜 $24M 강제청산 | DAI 연동 하락, USDT는 오히려 강세 전환 |

> FTX·LUNA 붕괴는 크립토 생태계 내 전이에 집중(BTC, ETH, DOGE, LTC 동반 하락)되고 S&P500(+0.48%), Nasdaq(+0.01%)은 통계적으로 무영향. **제도화 미완성 단계일수록 전통자산과의 디커플링 유지** → 헤지 구조 설계의 핵심 근거.

---

## 1-2. 크로스에셋 분석

### 이벤트별 자산군 반응 매트릭스

| 이벤트 | BTC | ETH | MARA/RIOT | COIN/MSTR | S&P500/Nasdaq | Gold | DXY |
|--------|-----|-----|-----------|-----------|----------------|------|-----|
| CME 선물 출시 (2017-12) | -2%→장기하락 | 동반하락 | N/A | N/A | 무반응 | 무반응 | 무반응 |
| Tesla 매수 (2021-02) | +17% | 동반상승 | 동반상승 | MSTR 급등 | 소폭 | 무반응 | 소폭 약세 |
| Coinbase IPO (2021-04) | $64,829 신고가 | 동반상승 | 동반상승 | COIN 상장 | 소폭 | 무반응 | 무반응 |
| LUNA 붕괴 (2022-05) | **-50%+** | **동반급락** | **동반급락** | **동반급락** | **소폭 약세** | **소폭 약세** | **강세** |
| FTX 붕괴 (2022-11) | **-25%** | **-30%** | **동반급락** | **COIN 채권 -15%** | **+0.48% (무영향)** | 무반응 | 강세 |
| Grayscale 판결 (2023-08) | +7.15% | 동반상승 | MARA +18%, RIOT +24% | COIN +13% | 무반응 | 무반응 | 소폭 약세 |
| 현물 ETF 승인 (2024-01) | 선반영 후 $73K | **+6.8%** | 동반상승 | 동반상승 | **상관계수 증가** | **상관계수 ~0** | 무반응 |
| USDC 디페깅 (2023-03) | 동반하락 | 동반하락 | 동반하락 | 동반하락 | 무반응 | 소폭 강세 | 강세 |

### 크립토 관련주 베타 구조

이벤트 발생 시 BTC보다 증폭된 반응을 보이는 레버리지 대리 자산군.

| 자산 | BTC 대비 Beta | 특징 |
|------|--------------|------|
| MARA | **2~4x** (시장 beta 5.34) | BTC -65% → MARA -90% / 상승기엔 역으로 초과 수익 |
| RIOT | **~3.8x** | MARA와 유사 구조, 고정비용 레버리지 |
| MSTR | **상관계수 ~0.6** | 고정 BTC 보유량 기반, 전환사채 구조 |
| COIN | **~1.2~1.5x** | 거래량 연동 → 변동성 이벤트에 민감 |

2023년 회복기: MARA +590%, RIOT +360% (BTC +155% 대비 초과) — 베타 증폭 확인

---

## 1-3. 매크로 분석

### 금리·통화정책 이벤트와 BTC 반응

| 이벤트 | BTC 반응 | 메커니즘 |
|--------|----------|---------|
| Fed 긴축 사이클 시작 (2022-03) | $48K → $16K (-67%) | 위험자산 회피, 국채 수익률 매력 상승 |
| CPI 9% YoY 발표 (2022-06) | -6% (3일 이내) | 추가 긴축 시그널 → 리스크 오프 |
| CPI 0.1% MoM (예상 0.3%, 2022-11) | +4% (2일 이내) | 긴축 완화 기대 → 리스크 온 |
| Fed 75bp 인상 (2022-11) | $18,300 → $20,500 일시 반등 | "예상 범위 내" → 불확실성 해소 효과 |

### BTC의 자산 성격 구조적 변화 (제도화 전후)

| 시기 | BTC 성격 | S&P500 상관계수 | DXY 상관계수 | Gold 상관계수 |
|------|----------|----------------|-------------|--------------|
| ~2019 | 무상관 독립 자산 | ~0 | ~0 | ~0.04 |
| 2020~2021 | 리스크자산화 시작 | +0.5 | -0.4 ~ -0.8 | ~0.04 |
| 2022 | 완전한 리스크자산 | **+0.89 (Nasdaq)** | -0.4 ~ -0.8 | ~0 |
| 2024~ | 제도화 완성 단계 | 유의하게 상승 | **양(+)으로 전환** | ~0 (안정) |

> BTC는 "디지털 골드"가 아닌 **고베타 기술주**처럼 움직임. 2022년 인플레이션 40년 최고치에도 BTC -75%, 금 보합 → 인플레이션 헤지 기능 부재 확인.

---

## 1-4. 국내 시장 특수성 — 김치 프리미엄

| 지표 | 수치 | 시사점 |
|------|------|--------|
| 2021-04-18 프리미엄 | **+20.6%** (업비트 vs Binance) | 국내 과열 → 글로벌 BTC 고점의 선행 경고 신호 |
| 2022-05/11 프리미엄 급등 | LUNA·FTX 붕괴 시 재급등 후 급락 | 국내 소매 패닉 증폭 효과 |
| 국내 암호화폐 보유 총액 (2024년 말) | **$76B** | 미국 이벤트 파급 규모 충분 |
| 국내 크립토 연간 거래액 (2022~2023) | **$111.82B** (동아시아 1위) | 일본·중국 초과 |
| 특정 일자 국내 거래량 | KOSPI 초과 발생 | 국내 투자자 집중도 확인 |

프리미엄 패턴: 글로벌 상승기 → 프리미엄 확대 → BTC 고점의 선행 경고 / 붕괴 이벤트 → 프리미엄 급등 후 급락 → 국내 증폭 효과. 자본 이동 규제($100K 한도)로 재정거래 제한 → 프리미엄 구조적 지속.

---

## 1-5. 백테스트 설계 방향

### 포함 자산군

| 분류 | 자산 | 포함 이유 |
|------|------|---------|
| 크립토 직접 | BTC, ETH, DOGE, LTC | 직접 충격 + 크립토 내 전이 효과 |
| 크립토 관련주 | MARA, RIOT, COIN, MSTR | BTC 대비 2~4x 베타 → 헤지 효율 |
| 매크로 지표 | Fed Funds Rate, CPI, DXY | 2020년 이후 BTC 매크로 민감도 급증 |
| 전통자산 | S&P500, Nasdaq, 국채 10년물 | 크립토 이벤트의 전통자산 전이 여부 검증 |
| 안전자산 | Gold | BTC-Gold 대체재 여부 (결론: 불가) |
| 국내 | 업비트/빗썸 BTC, KOSPI, 김치프리미엄 | 미국 이벤트 → 국내 반응 시차 분석 |

### 이벤트 윈도우 구조

```
[사전 선반영 구간]        [이벤트]        [사후 반응 구간]
T-180d ~ T-30d   →   T-5d ~ T+5d   →   T+5d ~ T+60d
(Announcement Drift)  (Event Window)   (Post-Event Drift)
```

### 핵심 검증 가설

1. 미국 제도화 이벤트 → 국내 시장의 유의한 동조화 반응이 존재한다
2. 이벤트 유형(긍정/부정)에 따라 크로스에셋 전이 범위가 다르다 (FTX: 크립토 내 한정 / Fed 긴축: 전통자산까지 동반)
3. 마이닝주·크립토 관련주는 BTC 이벤트의 증폭 헤지 수단으로 유효하다
4. 김치 프리미엄은 국내 가격 충격의 선행 지표로 활용 가능하다

---

# Part 2. 정성 분석: 스테이블코인 & RWA/STO

> Part 1의 정량 근거를 바탕으로, 국내 기업이 어떤 구조적 변화에 어떻게 포지셔닝해야 하는지를 분석한다.

---

## 2-1. 스테이블코인 제도화 흐름

### 글로벌 주요 이정표

| 날짜 | 이벤트 | 의미 |
|------|--------|------|
| 2022-05 | **LUNA/UST 붕괴** | 알고리즘형 스테이블코인의 구조적 한계 실증 → 담보형 스테이블코인 규제 논의 가속 |
| 2023-03 | **USDC/SVB 디페깅** (-13%, $0.87) | 은행 준비금 리스크 노출 → 준비금 투명성·다변화 요구 강화 |
| 2024-06 | **EU MiCA 스테이블코인 조항 발효** | USDT EU 거래소 상장 폐지, USDC가 기본 규제준수 옵션으로 부상 |
| 2025-07-18 | **미국 GENIUS Act 서명** | 세계 최초 연방 스테이블코인 법률. 1:1 준비금, 월간 공시, OCC 감독 의무화 |
| 2025-12 | **Circle·Paxos 등 5개사 OCC 국가 신탁은행 인가 취득** | 스테이블코인 발행사의 은행 수준 규제 편입 공식화 |

### GENIUS Act 핵심 내용 (미국 기준)

- **정의**: 결제·정산 목적, $1 고정 상환 가능한 디지털 자산
- **준비금**: 현금·단기 국채·MMF 등 고유동성 자산 1:1 보유 의무
- **공시**: 독립 회계법인 월간 감사 의무
- **지위**: 증권법(SEC)·상품법(CFTC) 적용 제외 → 결제 인프라로 분류
- **감독**: OCC(비은행 발행사), 연방·주 금융당국(은행 자회사)

### 디페깅 유형 분류 (리스크 관리 근거)

| 유형 | 사례 | 원인 | 회복 여부 |
|------|------|------|---------|
| 알고리즘형 완전 붕괴 | UST (2022-05) | 민트/번 메커니즘 데스스파이럴 | 회복 불가, 전액 손실 |
| 준비금 리스크 | USDC (2023-03) | SVB 예치금 동결 | 72시간 내 회복 (정부 보증) |
| 패닉성 일시 디페깅 | USDT (2022-05) | 시장 공포 전이 | 24시간 내 회복 |

---

## 2-2. 국내 스테이블코인 정책 및 기업 기회

### 규제 로드맵

- **2026년**: 디지털자산기본법 내 원화(KRW) 스테이블코인 발행 근거 입법 목표
- **핵심 쟁점**: 은행 주도 컨소시엄(지분 51%↑) vs. 핀테크 개방형 발행 — 한국은행(안정성)과 FSC(혁신) 대립 중
- **달러 스테이블코인(USDC/USDT) 규제**: FSC, 기업 디지털자산 투자 가이드라인에서 달러 스테이블코인 제외 방침 검토 중

### 국내 선점 움직임

| 주체 | 전략 |
|------|------|
| 신한·하나·우리·NH농협은행 공동 컨소시엄 | KRW 스테이블코인 공동 개발, 2025~2026년 출시 목표 |
| KRW1 (Sooho.io) | Woori Bank 에스크로 기반 원화 스테이블코인 POC 완료 |
| Plume Network + KRW1 | 글로벌 RWA 네트워크와 KRW 스테이블코인 연동 |

### 기업 대응 전략 방향

1. **단기**: GENIUS Act 기반 USDC 활용 — 글로벌 결제·정산 인프라로 편입 검토
2. **중기**: KRW 스테이블코인 발행 라이선스 확보 또는 은행 컨소시엄 참여 포지션 결정
3. **리스크 관리**: 준비금 구성 분산(단일 은행 집중 금지), 디페깅 이벤트 대응 프로토콜 수립

---

## 2-3. RWA/STO 제도화 흐름

### 글로벌 시장 현황

| 지표 | 수치 |
|------|------|
| 글로벌 RWA 토큰화 시장 규모 (2026년 초) | **$18.6B~$36B** (스테이블코인 제외) |
| McKinsey 2030년 전망 | **$2조** |
| 참여 기관 수 | 119개 이상 발행사 |
| 자산 유형 | 국채, 회사채, 사모대출, 부동산, 원자재, 주식, 사모펀드 |

### 글로벌 기관 주요 움직임

| 기관 | 행동 | 규모 |
|------|------|------|
| BlackRock | BUIDL 펀드 출시 (2024-03) | 6주 만에 토큰화 국채 시장 30% 점유, $2.5B+ |
| JP Morgan | Onyx 플랫폼 — 기관 간 토큰화 담보 결제 | 일일 수십억 달러 처리 |
| Goldman Sachs | GS DAP — 채권 토큰화 플랫폼 | 유럽투자은행 €1B 토큰 채권 발행 |
| Fidelity | 토큰화 MMF 출시 | 기관 유동성 관리 용도 |

### 국내 STO 제도화 로드맵 (FSC/FSS)

| 단계 | 시기 | 내용 |
|------|------|------|
| STO 플랫폼 인가 | 2025년 6월 | FSS, STO 플랫폼 사업자 인가 개시 |
| Phase 1 | 2027년 2월 | 사모 MMF, 회사채, 비상장주식, 조각투자 증권 토큰화 |
| Phase 2 | 2027년 이후 | 공모 증권 전체로 확대 |
| Phase 3 | 미정 | 온체인 결제 연동 (원화 스테이블코인 인프라 활용) |

프로젝트 한강(Project Hangang): 한국은행 주도, 토큰화 국채·CBDC·은행예금을 단일 분산원장으로 연결하는 원자적 결제(Atomic Settlement) 인프라 구축. Phase 1 (2025년 4~6월) 완료, Phase 2 (2026년 하반기) 예정.

### 국내 기업 경쟁 현황

| 진영 | 주체 | 전략 |
|------|------|------|
| KOSCOM 컨소시엄 | 증권사 다수 | 공동 STO 인프라 구축 |
| 신한투자증권 주도 | PULSE 플랫폼 | 2024년 자체 STO 생태계 구축, NXT(OTC 거래소) 지분 확보 |
| 미래에셋증권 | 단독 | 국내 인프라 우회, 홍콩에서 디지털 채권 직접 발행 |
| NH농협·우리은행 | 자체 STO 플랫폼 개발 중 | 규제 선도 포지션 |
| DB금융투자 | 부산·제주 STO 사업 확장 | 지역 특화 조각투자 |

---

## 2-4. 정성 분석 종합 — 국내 기업 전략 매트릭스

| 분야 | 단기 (2025~2026) | 중기 (2027~) | 리스크 |
|------|----------------|-------------|--------|
| **스테이블코인** | GENIUS Act 기반 USDC 결제 인프라 도입 검토 | KRW 스테이블코인 발행 라이선스 or 컨소시엄 참여 | 단일 은행 준비금 집중 리스크, 규제 주도권 불확실 |
| **STO** | STO 플랫폼 인가 참여 또는 제휴 | Phase 1 자산(회사채, MMF) 토큰화 발행 | 시장 유동성 부족, 투자자 교육 필요 |
| **RWA** | 해외 RWA 플랫폼(BlackRock BUIDL 등) 편입 검토 | 국내 부동산·채권 토큰화 발행 구조 설계 | 법적 소유권 구조 불명확, 온체인 분쟁 해결 미비 |
| **헤징** | Part 1 백테스트 결과 기반 BTC/ETH 가격 충격 헤지 운용 | 스테이블코인·RWA 포트폴리오의 디페깅 리스크 관리 체계 구축 | 규제 변화 속도 > 헤지 상품 개발 속도 |

---

## 참고 자료

**Part 1 — 정량 분석**
- [How Futures Trading Changed Bitcoin Prices (SF Fed)](https://www.frbsf.org/research-and-insights/publications/economic-letter/2018/05/how-futures-trading-changed-bitcoin-prices/)
- [Tesla buys $1.5B in bitcoin (CNBC)](https://www.cnbc.com/2021/02/08/tesla-buys-1point5-billion-in-bitcoin.html)
- [SEC Approves 11 Bitcoin Spot ETFs (Hunton)](https://www.hunton.com/blockchain-legal-resource/sec-approves-11-bitcoin-spot-etfs)
- [Bitcoin rallies 7% as court sides with Grayscale (CNBC)](https://www.cnbc.com/2023/08/29/bitcoin-rallies-more-than-5percent-as-court-sides-with-grayscale-over-the-sec-in-crypto-etf-case.html)
- [FTX collapse impact on traditional assets (Alpha Architect)](https://alphaarchitect.com/ftx-collapse/)
- [Why Bitcoin's Relationship with Equities Has Changed (CME Group)](https://www.cmegroup.com/openmarkets/economics/2025/Why-Bitcoins-Relationship-with-Equities-Has-Changed.html)
- [Impact of Bitcoin ETF Approval on Hedging Properties (arxiv)](https://arxiv.org/html/2512.12815v1)
- [Institutional Adoption and Correlation Dynamics (arxiv)](https://arxiv.org/pdf/2501.09911)
- [Bitcoin's reaction to FOMC and CPI (KSE)](https://kse.ua/wp-content/uploads/2026/05/illia-nazaruk_268722_assignsubmission_file_nazaruk_final_thesis.pdf)
- [Kimchi Premium spotlight (CNBC)](https://www.cnbc.com/2024/04/03/south-koreas-kimchi-premium-in-the-spotlight-after-btcs-record-highs.html)

**Part 2 — 정성 분석**
- [GENIUS Act signed into law (Mayer Brown)](https://www.mayerbrown.com/en/insights/publications/2025/07/genius-act-signed-into-law-us-enacts-federal-stablecoin-legislation)
- [USDC SVB depeg research (CryptoDaily)](https://cryptodaily.co.uk/2026/06/usdc-depeg-research-svb-lessons-stablecoin-risk)
- [Anatomy of Terra-Luna failure (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S1544612322005359)
- [EU MiCA stablecoin provisions (History of Stablecoins)](https://eco.com/support/en/articles/15210336-history-of-stablecoins-from-bitusd-to-the-genius-act)
- [BlackRock BUIDL tokenization (Boostylabs)](https://boostylabs.com/blog/blackrock-tokenization)
- [2024 RWA tokenization market recap (InvesTax)](https://investax.io/blog/2024-real-world-asset-tokenization-market-recap)
- [South Korea tokenized securities roadmap (CoinDesk)](https://www.coindesk.com/business/2026/09/04/south-korea-targets-february-2027-rollout-for-full-tokenized-securities-market)
- [Korea stablecoin moment (KoreaTechDesk)](https://koreatechdesk.com/korea-stablecoin-digital-asset-act-fintech-banks)
- [Korean companies digital asset strategy (Tiger Research)](https://reports.tiger-research.com/p/korea-institutional-crypto-2026-landscape-eng)
- [South Korea blockchain race (a16z crypto)](https://a16zcrypto.com/posts/article/south-korea-blockchain-race/)
- [Project Hangang tokenized bonds (CryptoTimes)](https://www.cryptotimes.io/2026/07/02/bank-of-korea-backs-tokenized-bonds-as-rwas-gain-momentum/)
