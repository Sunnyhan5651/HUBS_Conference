"""발행사 손익 + 플로어 전략 몬테카를로 (05번 노트북의 계산을 함수로 묶은 것).

단위: 금리 %, 금액 달러. 기간은 월간 36개월(3년), 연간 손익은 1~3년차 합계.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from src.floor_pricing import build_curve, monthly_forwards, price_floor, price_floor_later
from src.rate_model import simulate_market_consistent, simulate_vasicek

PROC_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
CURVE_IDS = ["DGS1MO", "DGS3MO", "DGS6MO", "DGS1", "DGS2", "DGS3", "DGS5", "DGS10"]
MATURITIES = np.array([1 / 12, 0.25, 0.5, 1, 2, 3, 5, 10])
MONTHS = 36
A_MIN = 1e-6   # a = 0(랜덤워크)은 공식에서 0으로 나누게 되므로 아주 작은 값으로 대신한다


def load_market():
    """보정 곡선(−(1개월 국채 − SOFR), PCHIP)과 월별 선도금리, 현재 SOFR."""
    rates = pd.read_parquet(PROC_DIR / "rates.parquet")
    row = rates[CURVE_IDS].dropna().iloc[-1]
    sofr = rates.loc[row.name, "SOFR"]
    shift = (row["DGS1MO"] - sofr) * 100
    curve = build_curve(row.values, MATURITIES, horizon=3.0, shift_bp=shift, method="pchip")
    fwd = monthly_forwards(row.values, MATURITIES, months=MONTHS, shift_bp=shift, method="pchip")
    return {"curve": curve, "fwd": fwd, "sofr": sofr, "date": row.name, "shift_bp": shift}


def load_issuer():
    """Circle 기준 고정비 C(달러/년)와 배분율 s."""
    p = pd.read_csv(PROC_DIR / "circle_params.csv", index_col=0)["value"]
    return float(p["C_musd_per_year"]) * 1e6, float(p["s"])


def simulate_rates(market, a, sigma, n_paths=10_000, seed=42, world="market", b=None):
    """금리 경로 (n_paths, 37).

    world="market": 시장 일치 모형 r = f(0, t) + x(t)  (메인)
    world="vasicek": 장기 평균 b로 끌려가는 Vasicek, 현재 SOFR에서 시작  (예: 스트레스 세계 C, b = 1.32%)
    """
    a = max(a, A_MIN)
    if world == "market":
        return simulate_market_consistent(market["fwd"], a, sigma, n_paths=n_paths, seed=seed)
    return simulate_vasicek(market["sofr"], a, b, sigma, months=MONTHS, n_paths=n_paths, seed=seed)


def to_years(monthly_cash):
    """(경로, 36개월) → (경로, 3년) 연간 합계."""
    year = np.arange(MONTHS) // 12
    return np.stack([monthly_cash[:, year == y].sum(axis=1) for y in range(3)], axis=1)


def evaluate_strategies(paths, market, R, C, s, rstar, a_price, sigma_price,
                        tc_bp=2.0, hedge_ratios=None, strike_offsets=(-1.0, -0.5, 0.0, 0.5),
                        tenors=("1년 롤링", "3년"), g=0.0, yield_gap=0.15, return_annual=False):
    """규모 하나에 대해 무헤지 + 플로어 전략들의 손실확률·비용을 계산한다.

    반환: (결과 DataFrame, {전략 이름: 경로별 '한 해라도 적자' 여부 배열})
    - 손실확률: 3년 중 한 해라도 연간 손익 < 0 인 경로 비율 (%)
    - 3년 만기 보험료는 3년에 고르게 나눠 비용 처리, 롤링은 산 해에 전부
    - hedge_ratios를 주지 않으면 메인 후보 {1 − s, 50%, 100%}
    - return_annual=True면 두 번째 반환값이 {전략 이름: 경로별 연간 손익 (경로, 3년)} 이 된다 (해별 적자확률용)
    """
    if hedge_ratios is None:
        hedge_ratios = (round(1 - s, 3), 0.5, 1.0)
    a_price = max(a_price, A_MIN)
    n_paths = paths.shape[0]
    r = paths[:, :MONTHS]
    x_state = paths - market["fwd"][np.newaxis, :]          # 시장이 보는 '선도금리 대비 어긋남'
    k = np.arange(MONTHS)

    reserve_yield = np.maximum(r, 0) - yield_gap
    base = to_years((1 - s) * reserve_yield / 100 * R * np.exp(g * k) / 12 - C / 12)

    rows, flags = [], {}

    def record(name, K, off, h, tenor, premium, tcost, payoff):
        annual = base + payoff - premium - tcost
        flag = (annual < 0).any(axis=1)
        flags[name] = annual if return_annual else flag
        rows.append({
            "전략": name, "K": K, "K−r*": off, "h": h, "만기": tenor,
            "손실확률(%)": flag.mean() * 100,
            "참고: 3년 누적(%)": (annual.sum(axis=1) < 0).mean() * 100,
            "보험료(백만$)": premium.sum(axis=1).mean() / 1e6,
            "거래비용(백만$)": tcost.sum() / 1e6,
            "총 헤지 비용(백만$)": (premium.sum(axis=1).mean() + tcost.sum()) / 1e6,
        })

    zeros = np.zeros((n_paths, 3))
    record("무헤지", None, None, None, None, zeros, np.zeros(3), zeros)
    for off in strike_offsets:
        K = round(rstar + off, 3)
        for h in hedge_ratios:
            N = h * R
            payoff = to_years(N * np.maximum(K - r, 0) / 100 / 12)
            tcost = np.full(3, N * tc_bp / 10_000)
            for tenor in tenors:
                if tenor == "3년":
                    total = price_floor(market["curve"], K, 3, sigma_price, a=a_price)[0]["floor"] * N / 100
                    premium = np.full((n_paths, 3), total / 3)
                else:
                    premium = np.stack([
                        price_floor_later(market["curve"], y, x_state[:, 12 * y], K, 1, sigma_price, a_price) * N / 100
                        for y in range(3)], axis=1)
                name = f"K r*{off:+.1f} ({K:.2f}%) h{h * 100:g} {tenor}"
                record(name, K, off, h, tenor, premium, tcost, payoff)
    return pd.DataFrame(rows), flags


def pick_optimal(results, limit=5.0):
    """손실확률 ≤ limit 중 총 헤지 비용이 가장 작은 전략 (없으면 None)."""
    ok = results[results["손실확률(%)"] <= limit]
    return ok.sort_values(["총 헤지 비용(백만$)", "손실확률(%)"]).iloc[0] if len(ok) else None


def wilson_interval(p_hat, n, z=1.96):
    """비율의 95% 신뢰구간 (Wilson 방식, 0% 근처에서도 쓸 수 있음). 입력·출력 단위는 비율(0~1)."""
    center = (p_hat + z ** 2 / (2 * n)) / (1 + z ** 2 / n)
    half = z * np.sqrt(p_hat * (1 - p_hat) / n + z ** 2 / (4 * n ** 2)) / (1 + z ** 2 / n)
    return center - half, center + half
