"""금리 플로어 가격: 수익률곡선 → 할인계수·선도금리 → 바슐리에(정규) 모형.

단위: 금리·행사가·σ는 모두 % (예: 4.2, 0.64). 가격은 명목금액 100 기준.
"""
import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator
from scipy.stats import norm

TAU = 0.25   # 분기 = 0.25년


def zero_rates_from_cmt(yields_pct, maturities):
    """국채 수익률(CMT, %)을 연속복리 영(zero)금리(%)로 근사한다.

    6개월 이하(단기 국채)는 단리, 1년 이상은 반년 복리로 보고 연속복리로 바꾼다.
    1년 이상은 이표채 수익률(par)을 영금리로 그대로 쓰는 근사다.
    """
    y = np.asarray(yields_pct, dtype=float) / 100
    t = np.asarray(maturities, dtype=float)
    z = np.where(t <= 0.5, np.log(1 + y * t) / t, 2 * np.log(1 + y / 2))
    return z * 100


def zero_curve(yields_pct, maturities, shift_bp=0.0, method="linear"):
    """영금리 곡선 z(t)(%)를 돌려주는 함수를 만든다.

    shift_bp: 국채 수익률 전체에서 뺄 값(bp). 국채−SOFR 차이를 빼서 SOFR 기준으로 맞추는 보정
    method:   "linear" = 만기 사이를 직선으로 잇기, "pchip" = 꺾이지 않게 부드럽게 잇기(PCHIP)
    """
    shifted = np.asarray(yields_pct, dtype=float) - shift_bp / 100
    zeros = zero_rates_from_cmt(shifted, maturities)
    if method == "pchip":
        return PchipInterpolator(maturities, zeros)
    return lambda t: np.interp(t, maturities, zeros)


def discount_factors(zfunc, t):
    """할인계수 D(t) = e^(−z(t) × t). t = 0이면 1."""
    t = np.asarray(t, dtype=float)
    return np.exp(-zfunc(t) / 100 * t)


def period_forwards(zfunc, t):
    """시점 t[0], t[1], ... 사이 구간마다의 단리 선도금리(%)."""
    D = discount_factors(zfunc, t)
    return (D[:-1] / D[1:] - 1) / np.diff(t) * 100


def build_curve(yields_pct, maturities, horizon=3.0, tau=TAU, shift_bp=0.0, method="linear"):
    """분기 간격의 할인계수와 분기 선도금리 표를 만든다.

    반환 DataFrame (분기 i = 1..n 한 줄씩):
      start, end: 분기의 시작·끝 시점(년), D_end: 끝 시점 할인계수,
      forward: 그 분기의 단리 선도금리(%)
    """
    zfunc = zero_curve(yields_pct, maturities, shift_bp, method)
    t = np.arange(0, horizon + 1e-9, tau)
    D = discount_factors(zfunc, t)                # 할인계수 = e^(−영금리 × 기간)
    return pd.DataFrame({
        "start": t[:-1], "end": t[1:], "zero_end": zfunc(t[1:]), "D_end": D[1:],
        "forward": period_forwards(zfunc, t),     # 분기 선도금리 (단리, %)
    }, index=pd.RangeIndex(1, len(t), name="분기"))


def monthly_forwards(yields_pct, maturities, months=36, shift_bp=0.0, method="pchip"):
    """시장 일치 시뮬레이션용: k번째 달(k = 0..months)에 적용될 1개월 선도금리(%) 배열.

    길이는 months + 1. 0번째 값이 '지금부터 1개월' 금리라서 보정 후에는 현재 SOFR와 비슷해야 한다.
    """
    zfunc = zero_curve(yields_pct, maturities, shift_bp, method)
    t = np.arange(0, months + 2) / 12
    return period_forwards(zfunc, t)


def bachelier(F, K, sigma, T, kind="floor"):
    """바슐리에(정규) 모형의 옵션 값 (할인 전, % 단위).

    floor(풋):  (K − F)·Φ(d) + σ√T·φ(d),  d = (K − F) / (σ√T)
    cap(콜):    (F − K)·Φ(−d) + σ√T·φ(d)
    """
    s = sigma * np.sqrt(T)
    d = (K - F) / s
    if kind == "floor":
        return (K - F) * norm.cdf(d) + s * norm.pdf(d)
    return (F - K) * norm.cdf(-d) + s * norm.pdf(d)


def equivalent_sigma(T, a, sigma):
    """평균회귀(속도 a)가 있을 때의 바슐리에 등가 σ = σ·√((1 − e^(−2aT)) / (2aT)).

    시장 일치 모형 r = f + x(Vasicek 충격)의 T년 뒤 퍼짐과 정확히 같은 퍼짐을 주는 σ.
    """
    T = np.asarray(T, dtype=float)
    return sigma * np.sqrt((1 - np.exp(-2 * a * T)) / (2 * a * T))


def price_floor(curve, K, maturity, sigma, notional=100, tau=TAU, a=None):
    """만기 maturity(년)까지의 분기 플로어렛을 모두 더해 플로어·캡·리시버 스왑 가치를 낸다.

    SOFR 플로어는 분기 동안의 SOFR를 복리로 평균해 분기 끝에 정산한다(후취).
    분기 중에도 금리가 움직이므로, 옵션 만기를 '분기 시작 + 분기 길이의 1/3'로 잡아 그 몫을 반영한다.
    a: 주면 플로어렛마다 등가 σ(평균회귀 반영)를 쓴다 (메인). None이면 σ를 그대로 쓴다 (부록).
    반환: (요약 딕셔너리, 플로어렛 표)
    """
    legs = curve[curve["end"] <= maturity + 1e-9].copy()
    legs["T_eff"] = legs["start"] + tau / 3
    legs["sigma"] = equivalent_sigma(legs["T_eff"], a, sigma) if a is not None else sigma
    scale = notional / 100 * tau * legs["D_end"]            # 명목 × 기간 × 할인 (금리 % → 금액)
    legs["floorlet"] = scale * bachelier(legs["forward"], K, legs["sigma"], legs["T_eff"], "floor")
    legs["caplet"] = scale * bachelier(legs["forward"], K, legs["sigma"], legs["T_eff"], "cap")
    legs["swaplet"] = scale * (K - legs["forward"])         # 고정 K 받고 변동금리 내는 쪽

    summary = {
        "floor": legs["floorlet"].sum(),
        "cap": legs["caplet"].sum(),
        "receiver_swap": legs["swaplet"].sum(),
        "annuity": (notional / 100 * tau * legs["D_end"]).sum(),   # 스왑 1%p당 가치
    }
    return summary, legs


def price_floor_later(curve, t0, x, K, years, sigma, a, tau=TAU):
    """미래 시점 t0(년)에 '그때 금리 상태'로 years년짜리 플로어를 새로 살 때의 가격 (명목 100당).

    시장 일치 모형에서 t0 시점의 선도금리를 f(t0, T) = f(0, T) + x(t0)·e^(−a(T − t0)) 로 근사한다.
    x: 경로별 충격 x(t0) 배열 → 경로별 가격 배열을 돌려준다. 할인도 조정된 선도금리로 한다.
    """
    legs = curve[(curve["start"] >= t0 - 1e-9) & (curve["end"] <= t0 + years + 1e-9)]
    x = np.atleast_1d(np.asarray(x, dtype=float))[:, np.newaxis]
    until = legs["start"].to_numpy() - t0                                   # t0부터 각 분기 시작까지
    F = legs["forward"].to_numpy()[np.newaxis, :] + x * np.exp(-a * until)[np.newaxis, :]
    D = np.cumprod(1 / (1 + tau * F / 100), axis=1)                         # t0 기준 할인계수
    T = until + tau / 3
    vol = equivalent_sigma(T, a, sigma)[np.newaxis, :]
    return (tau * D * bachelier(F, K, vol, T[np.newaxis, :], "floor")).sum(axis=1)


def vasicek_expected_path(r0, a, b, t):
    """Vasicek 모형의 기대 금리 경로 E[r(t)] = b + (r0 − b)·e^(−a·t)."""
    return b + (r0 - b) * np.exp(-a * np.asarray(t))
