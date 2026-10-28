"""Vasicek 금리 모형: 월간 데이터로 추정(AR(1))하고, 금리 경로를 시뮬레이션한다.

Vasicek 모형:  dr = a·(b − r)·dt + σ·dW
  a: 평균회귀 속도, b: 장기 평균(%), σ: 변동성(%p / √년)
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm

DT = 1 / 12   # 한 달 = 1/12년


def fit_vasicek(r, dt=DT):
    """월간 금리 r(%, pandas Series)로 Vasicek 파라미터를 추정한다.

    r(t+1) = c + φ·r(t) + e 를 회귀(AR(1))한 뒤 Vasicek 파라미터로 바꾼다.
      a = −ln(φ) / dt,  b = c / (1 − φ),  σ = sd(e) · √(2a / (1 − φ²))
    반환: (파라미터 딕셔너리, 잔차 Series)
    """
    y = r.iloc[1:].to_numpy()    # 다음 달 금리
    x = r.iloc[:-1].to_numpy()   # 이번 달 금리
    res = sm.OLS(y, sm.add_constant(x)).fit()
    c, phi = res.params
    if not 0 < phi < 1:
        raise ValueError(f"φ = {phi:.4f}: 평균회귀가 없어 Vasicek으로 바꿀 수 없음")

    a = -np.log(phi) / dt
    b = c / (1 - phi)
    resid = pd.Series(res.resid, index=r.index[1:])
    sigma = sigma_from_resid(resid, a, phi)
    params = {
        "phi": phi, "a": a, "b": b, "sigma": sigma,
        "half_life_months": np.log(2) / a * 12,   # 평균과의 거리가 절반으로 줄어드는 데 걸리는 개월 수
        "n": len(y), "start": r.index[0].date(), "end": r.index[-1].date(),
    }
    return params, resid


def sigma_from_resid(resid, a, phi):
    """월간 잔차의 표준편차를 연 단위 Vasicek σ로 바꾼다."""
    return resid.std() * np.sqrt(2 * a / (1 - phi ** 2))


def bond_B(tau, a):
    """Vasicek 채권가격 공식의 B(τ) = (1 − e^(−aτ)) / a.  y_τ의 단기금리 민감도는 B(τ)/τ."""
    return (1 - np.exp(-a * tau)) / a


def simulate_vasicek(r0, a, b, sigma, months=36, n_paths=1000, seed=42, dt=DT):
    """r0(%)에서 시작하는 월간 금리 경로를 정확한 이산화로 만든다.

    r(t+1) = b + (r(t) − b)·e^(−a·dt) + σ·√((1 − e^(−2a·dt)) / (2a))·Z,  Z ~ 표준정규
    반환: (n_paths, months + 1) 배열. 첫 열은 r0
    """
    rng = np.random.default_rng(seed)      # seed를 고정하면 매번 같은 경로가 나온다
    decay = np.exp(-a * dt)
    step_sd = sigma * np.sqrt((1 - decay ** 2) / (2 * a))

    paths = np.empty((n_paths, months + 1))
    paths[:, 0] = r0
    for t in range(months):
        paths[:, t + 1] = b + (paths[:, t] - b) * decay + step_sd * rng.standard_normal(n_paths)
    return paths
