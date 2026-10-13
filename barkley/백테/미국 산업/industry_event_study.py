"""
미국 크립토 제도화 이벤트 → 미국 산업별 주가 반응 이벤트 스터디 (Fama-French 49 산업, 일별)

실행:  python industry_event_study.py            # data/raw에 zip이 있으면 재사용, 없으면 다운로드
       python industry_event_study.py --refresh  # Kenneth French Data Library에서 새로 다운로드

입력:  최종_이벤트_리스트.xlsx (같은 폴더)
출력:  data/   : 산업 일별 수익률·시장 수익률 CSV
       results/: AR·CAR·검정 결과 CSV, 요약 엑셀, 그림 3개(PNG)

다운로드가 막히면 아래 두 zip을 브라우저로 받아 data/raw/에 넣고 다시 실행하면 됨
  https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/49_Industry_Portfolios_daily_CSV.zip
  https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip
"""
import argparse
import io
import os
import re
import urllib.request
import warnings
import zipfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from scipy import stats

warnings.filterwarnings("ignore", message="Mean of empty slice")
warnings.filterwarnings("ignore", message="Degrees of freedom")

# ============================================================
# 설정
# ============================================================
BASE = os.path.dirname(os.path.abspath(__file__))
RAW, DATA, OUT = os.path.join(BASE, "data", "raw"), os.path.join(BASE, "data"), os.path.join(BASE, "results")
EVENT_FILE = os.path.join(BASE, "최종_이벤트_리스트.xlsx")

FF_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FILES = {"ind": "49_Industry_Portfolios_daily_CSV.zip", "fac": "F-F_Research_Data_Factors_daily_CSV.zip"}
START = "2016-01-01"

EST_START, EST_END = -125, -6          # 추정 구간(시장 모형 추정): 120거래일
W = 5                                  # 이벤트 구간 [-5, +5]
WINDOWS = {"[-5,+5]": (-5, 5), "[-1,+1]": (-1, 1), "[0,0]": (0, 0)}
REPORT_WINDOWS = ["[-1,+1]", "[-5,+5]"]
N_SIM = 2000
GROUPS = ["통합(방향 보정)", "긍정(+1)", "부정(-1)"]
# 스테이블코인·크립토 제도화와 관련이 큰 산업 (그림 2·3에 사용)
FOCUS = ["Banks", "Fin", "Insur", "RlEst", "BusSv", "Softw", "Hardw", "Chips", "Telcm", "Rtail", "Util", "Gold"]
KOR = {"Banks": "은행", "Fin": "기타금융(증권·운용·결제)", "Insur": "보험", "RlEst": "부동산", "BusSv": "비즈니스 서비스",
       "Softw": "소프트웨어", "Hardw": "컴퓨터 하드웨어", "Chips": "반도체", "Telcm": "통신", "Rtail": "소매",
       "Util": "유틸리티", "Gold": "금광"}

for f in ["Malgun Gothic", "AppleGothic", "NanumGothic", "Noto Sans CJK KR"]:
    if any(f == x.name for x in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = f
        break
plt.rcParams["axes.unicode_minus"] = False

FOMC = pd.to_datetime([
    "2017-02-01", "2017-03-15", "2017-05-03", "2017-06-14", "2017-07-26", "2017-09-20", "2017-11-01", "2017-12-13",
    "2018-01-31", "2018-03-21", "2018-05-02", "2018-06-13", "2018-08-01", "2018-09-26", "2018-11-08", "2018-12-19",
    "2019-01-30", "2019-03-20", "2019-05-01", "2019-06-19", "2019-07-31", "2019-09-18", "2019-10-30", "2019-12-11",
    "2020-01-29", "2020-03-03", "2020-03-15", "2020-04-29", "2020-06-10", "2020-07-29", "2020-09-16", "2020-11-05", "2020-12-16",
    "2021-01-27", "2021-03-17", "2021-04-28", "2021-06-16", "2021-07-28", "2021-09-22", "2021-11-03", "2021-12-15",
    "2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15", "2022-07-27", "2022-09-21", "2022-11-02", "2022-12-14",
    "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14", "2023-07-26", "2023-09-20", "2023-11-01", "2023-12-13",
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12", "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29", "2026-09-16",
])
CPI = pd.to_datetime([
    "2017-01-18", "2017-02-15", "2017-03-15", "2017-04-14", "2017-05-12", "2017-06-14", "2017-07-14", "2017-08-11", "2017-09-14", "2017-10-13", "2017-11-15", "2017-12-13",
    "2018-01-12", "2018-02-14", "2018-03-13", "2018-04-11", "2018-05-10", "2018-06-12", "2018-07-12", "2018-08-10", "2018-09-13", "2018-10-11", "2018-11-14", "2018-12-12",
    "2019-01-11", "2019-02-13", "2019-03-12", "2019-04-10", "2019-05-10", "2019-06-12", "2019-07-11", "2019-08-13", "2019-09-12", "2019-10-10", "2019-11-13", "2019-12-11",
    "2020-01-14", "2020-02-13", "2020-03-11", "2020-04-10", "2020-05-12", "2020-06-10", "2020-07-14", "2020-08-12", "2020-09-11", "2020-10-13", "2020-11-12", "2020-12-10",
    "2021-01-13", "2021-02-10", "2021-03-10", "2021-04-13", "2021-05-12", "2021-06-10", "2021-07-13", "2021-08-11", "2021-09-14", "2021-10-13", "2021-11-10", "2021-12-10",
    "2022-01-12", "2022-02-10", "2022-03-10", "2022-04-12", "2022-05-11", "2022-06-10", "2022-07-13", "2022-08-10", "2022-09-13", "2022-10-13", "2022-11-10", "2022-12-13",
    "2023-01-12", "2023-02-14", "2023-03-14", "2023-04-12", "2023-05-10", "2023-06-13", "2023-07-12", "2023-08-10", "2023-09-13", "2023-10-12", "2023-11-14", "2023-12-12",
    "2024-01-11", "2024-02-13", "2024-03-12", "2024-04-10", "2024-05-15", "2024-06-12", "2024-07-11", "2024-08-14", "2024-09-11", "2024-10-10", "2024-11-13", "2024-12-11",
    "2025-01-15", "2025-02-12", "2025-03-12", "2025-04-10", "2025-05-13", "2025-06-11", "2025-07-15", "2025-08-12", "2025-09-11", "2025-10-24", "2025-12-18",
    "2026-01-13", "2026-02-13", "2026-03-11", "2026-04-10", "2026-05-12", "2026-06-10", "2026-07-14", "2026-08-12", "2026-09-11",
])


# ============================================================
# Step 1. Fama-French 데이터 다운로드·읽기
#   - 49 산업 가치가중(value-weighted) 일별 수익률 + 시장 수익률(Mkt-RF + RF)
#   - 단위: % (예: 1.25 = 1.25%), -99.99 = 결측
# ============================================================
def download(refresh=False):
    os.makedirs(RAW, exist_ok=True)
    for name in FILES.values():
        path = os.path.join(RAW, name)
        if os.path.exists(path) and not refresh:
            continue
        req = urllib.request.Request(FF_URL + name, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r, open(path, "wb") as f:
            f.write(r.read())
        print(f"[Step 1] 다운로드: {name}")


def read_ff_zip(path):
    """French 라이브러리 CSV에서 첫 번째 표(가치가중)만 읽음"""
    with zipfile.ZipFile(path) as z:
        text = z.read(z.namelist()[0]).decode("latin-1")
    lines = text.splitlines()
    h = next(i for i, l in enumerate(lines) if l.strip().startswith(","))
    body = [lines[h]]
    for l in lines[h + 1:]:
        if re.match(r"^\s*\d{8}\s*,", l):
            body.append(l)
        elif len(body) > 1:
            break                                           # 다음 표(동일가중)가 시작되면 멈춤
    df = pd.read_csv(io.StringIO("\n".join(body)), index_col=0)
    df.index = pd.to_datetime(df.index.astype(str).str.strip(), format="%Y%m%d")
    df.index.name = "date"
    df.columns = [c.strip() for c in df.columns]
    return df.replace([-99.99, -999], np.nan)


def step1_data(refresh=False):
    download(refresh)
    ind = read_ff_zip(os.path.join(RAW, FILES["ind"])).loc[START:]
    fac = read_ff_zip(os.path.join(RAW, FILES["fac"])).loc[START:]
    mkt = (fac["Mkt-RF"] + fac["RF"]).rename("MKT")         # 시장 전체 수익률
    ind, mkt = ind.align(mkt, join="inner", axis=0)
    ind.to_csv(os.path.join(DATA, "ff49_industry_daily.csv"))
    fac.to_csv(os.path.join(DATA, "ff_factors_daily.csv"))
    print(f"[Step 1] 산업 {ind.shape[1]}개, {ind.index.min():%Y-%m-%d} ~ {ind.index.max():%Y-%m-%d} ({len(ind)}거래일)")
    return ind, mkt


# ============================================================
# Step 2. 이벤트 날짜를 거래일(t0)에 맞추기
#   - '미국 주식 t0' 사용 (장 마감 후·주말 발표는 이미 다음 거래일), 공휴일이면 다음 거래일
#   - 데이터 끝(French 라이브러리는 1~2개월 늦게 갱신)보다 뒤인 이벤트는 자동 제외
# ============================================================
def step2_events(dates):
    raw = pd.read_excel(EVENT_FILE, sheet_name="이벤트 리스트")
    dir_col = [c for c in raw.columns if "방향" in c][0]
    ev = raw.loc[raw["표본"] == "Main", ["이벤트 ID", "미국 주식 t0", "이벤트", dir_col]]
    ev.columns = ["event_id", "t0_list", "title", "direction"]
    ev["t0_list"] = pd.to_datetime(ev["t0_list"])
    ev["t0_pos"] = dates.searchsorted(ev["t0_list"])
    dropped = ev[ev["t0_pos"] + W >= len(dates)]
    ev = ev[ev["t0_pos"] + W < len(dates)].copy()
    ev["t0"] = dates[ev["t0_pos"]]
    if len(dropped):
        print(f"[Step 2] 데이터 기간 밖이라 제외: {', '.join(dropped['event_id'])}")
    print(f"[Step 2] 분석 이벤트 {len(ev)}개 (긍정 {(ev['direction'] == 1).sum()} / 부정 {(ev['direction'] == -1).sum()})")
    return ev.reset_index(drop=True)


# ============================================================
# Step 3. 시장 모형으로 AR·CAR 계산
#   - 추정 구간에서 R_산업 = α + β·R_시장 회귀 → 정상 수익률 = α + β·(그날 시장 수익률)
#   - AR = 실제 - 정상 ("시장 전체 움직임을 뺀 그 산업만의 추가 움직임"), CAR = 구간 합
# ============================================================
def step3_car(ind, mkt, ev):
    rows = []
    for _, e in ev.iterrows():
        est = slice(max(0, e["t0_pos"] + EST_START), e["t0_pos"] + EST_END + 1)
        rm_est = mkt.iloc[est]
        for k in ind.columns:
            ri_est = ind[k].iloc[est]
            ok = ri_est.notna() & rm_est.notna()
            if ok.sum() < 60:
                continue
            beta, alpha = np.polyfit(rm_est[ok], ri_est[ok], 1)
            resid_sd = (ri_est[ok] - alpha - beta * rm_est[ok]).std(ddof=2)
            for tau in range(-W, W + 1):
                p = e["t0_pos"] + tau
                rows.append({"event_id": e["event_id"], "ind": k, "tau": tau,
                             "AR": ind[k].iloc[p] - (alpha + beta * mkt.iloc[p]),
                             "alpha": alpha, "beta": beta, "est_sd": resid_sd})
    ar = pd.DataFrame(rows)
    cars = []
    for wname, (a, b) in WINDOWS.items():
        g = ar[(ar["tau"] >= a) & (ar["tau"] <= b)].groupby(["event_id", "ind"])
        s = g.agg(CAR=("AR", lambda x: x.sum(min_count=1)), L=("AR", "count"), est_sd=("est_sd", "first")).reset_index()
        s["window"] = wname
        cars.append(s)
    car = pd.concat(cars).merge(ev[["event_id", "title", "direction"]], on="event_id")
    car["SCAR"] = car["CAR"] / (car["est_sd"] * np.sqrt(car["L"]))
    ar.to_csv(os.path.join(OUT, "industry_AR.csv"), index=False)
    car.to_csv(os.path.join(OUT, "industry_CAR.csv"), index=False)
    print(f"[Step 3] AR·CAR 계산 완료 (이벤트 {ev.shape[0]} × 산업 {ar['ind'].nunique()})")
    return ar, car


# ============================================================
# Step 4. 오염 판정 (구간 안에 FOMC 결정일·CPI 발표일이 있으면 오염)
# ============================================================
def step4_overlap(ev, dates):
    def hits(p, a, b):
        lo, hi = dates[max(0, p + a)], dates[min(len(dates) - 1, p + b)]
        return ", ".join([f"FOMC {d:%m/%d}" for d in FOMC if lo <= d <= hi] + [f"CPI {d:%m/%d}" for d in CPI if lo <= d <= hi])
    for wname, (a, b) in WINDOWS.items():
        ev[f"overlap_{wname}"] = [hits(p, a, b) for p in ev["t0_pos"]]
        ev[f"clean_{wname}"] = ev[f"overlap_{wname}"] == ""
    ev.to_csv(os.path.join(OUT, "events_overlap_check.csv"), index=False, encoding="utf-8-sig")
    print("[Step 4] 오염 제외 표본: " + ", ".join(f"{w} {ev[f'clean_{w}'].sum()}개" for w in REPORT_WINDOWS))
    return ev


# ============================================================
# Step 5. 통계 검정 (방향 보정 + BMP + 부호 + placebo + FDR)
#   - 방향 보정: 부정(-1) 이벤트 CAR × (-1) → 긍정과 합쳐 "진전이면 한쪽, 후퇴면 반대쪽"을 검정
#   - placebo: 이벤트 없는 날을 무작위로 뽑아 같은 시장 모형 CAR을 2,000번 계산해 비교
#   - FDR: 49개 산업을 동시에 검정한 것을 보정 (Benjamini-Hochberg)
# ============================================================
def bh_q(p):
    p = np.asarray(p, float); n = len(p); o = np.argsort(p)
    r = np.minimum.accumulate((p[o] * n / np.arange(1, n + 1))[::-1])[::-1]
    q = np.empty(n); q[o] = np.minimum(r, 1)
    return q


_PL = {}


def placebo_car(ind, mkt, window, cand):
    """모든 날짜를 t0로 가정한 시장 모형 CAR을 한 번에 계산 (rolling 회귀)"""
    if window in _PL:
        return _PL[window]
    a, b = WINDOWS[window]
    n = b - a + 1
    m_rm = mkt.rolling(120, min_periods=60).mean()
    v_rm = mkt.rolling(120, min_periods=60).var()
    m_ri = ind.rolling(120, min_periods=60).mean()
    cov = ind.rolling(120, min_periods=60).cov(mkt)
    beta = (cov.div(v_rm, axis=0)).shift(6)
    alpha = (m_ri - cov.div(v_rm, axis=0).mul(m_rm, axis=0)).shift(6)
    s_ri = ind.rolling(n, min_periods=max(1, n - 2)).sum().shift(-b)
    s_rm = mkt.rolling(n).sum().shift(-b)
    cnt = ind.notna().rolling(n).sum().shift(-b)
    car = s_ri - cnt * alpha - beta.mul(s_rm, axis=0)
    _PL[window] = car.iloc[cand].to_numpy()
    return _PL[window]


def run_tests(car, ev, ind, mkt, window, ids, group, cand, seed=42):
    d = car[(car["window"] == window) & car["event_id"].isin(ids)].copy()
    if group == "긍정(+1)":
        d = d[d["direction"] == 1]; d["sgn"] = 1
    elif group == "부정(-1)":
        d = d[d["direction"] == -1]; d["sgn"] = 1
    else:
        d = d[d["direction"] != 0]; d["sgn"] = d["direction"]
    evs = d["event_id"].unique()
    dirs = ev.set_index("event_id").loc[evs, "direction"].to_numpy() if group == "통합(방향 보정)" else np.ones(len(evs))
    pl = placebo_car(ind, mkt, window, cand)
    rng = np.random.default_rng(seed)
    sims = np.nanmean(pl[rng.integers(0, len(cand), size=(N_SIM, len(dirs)))] * dirs[None, :, None], axis=1) if len(dirs) else None

    rows = []
    for j, k in enumerate(ind.columns):
        x = d[d["ind"] == k]
        v, z = (x["CAR"] * x["sgn"]).dropna().to_numpy(), (x["SCAR"] * x["sgn"]).dropna().to_numpy()
        n = len(v)
        if n >= 3:
            se, tc = v.std(ddof=1) / np.sqrt(n), stats.t.ppf(0.975, n - 1)
            nz = v[v != 0]
            res = dict(mean=v.mean(), lo=v.mean() - tc * se, hi=v.mean() + tc * se,
                       p_bmp=stats.ttest_1samp(z, 0).pvalue,
                       p_sign=stats.binomtest(int((nz > 0).sum()), len(nz), 0.5).pvalue,
                       p_placebo=np.mean(np.abs(sims[:, j]) >= abs(v.mean())))
        else:
            res = dict(mean=np.nan, lo=np.nan, hi=np.nan, p_bmp=np.nan, p_sign=np.nan, p_placebo=np.nan)
        rows.append({"ind": k, "N": n, **res})
    out = pd.DataFrame(rows)
    ok = out["p_bmp"].notna()
    out["q_fdr"] = np.nan
    out.loc[ok, "q_fdr"] = bh_q(out.loc[ok, "p_bmp"])
    return out


def step5_tests(car, ev, ind, mkt):
    excl = set()
    for p in ev["t0_pos"]:
        excl.update(range(p - 10, p + 11))
    cand = np.array([i for i in range(130, len(ind) - W - 1) if i not in excl])
    res = []
    for w in REPORT_WINDOWS:
        for sample in ["전체", "오염 제외"]:
            ids = ev["event_id"] if sample == "전체" else ev.loc[ev[f"clean_{w}"], "event_id"]
            for g in GROUPS:
                r = run_tests(car, ev, ind, mkt, w, list(ids), g, cand)
                r.insert(0, "group", g); r.insert(0, "sample", sample); r.insert(0, "window", w)
                res.append(r)
    res = pd.concat(res, ignore_index=True)
    res.to_csv(os.path.join(OUT, "industry_tests.csv"), index=False, encoding="utf-8-sig")
    top = res[(res["window"] == REPORT_WINDOWS[0]) & (res["sample"] == "전체") & (res["group"] == "통합(방향 보정)")]
    sig = top[top["p_bmp"] < 0.05].sort_values("p_bmp")
    print(f"[Step 5] {REPORT_WINDOWS[0]} 통합 전체 표본: BMP p<0.05 산업 {len(sig)}개, FDR q<0.05 산업 {(top['q_fdr'] < 0.05).sum()}개")
    for _, r in sig.iterrows():
        print(f"         {r['ind']:6s} 평균 {r['mean']:+.2f}%  p={r['p_bmp']:.3f}  q={r['q_fdr']:.3f}  placebo={r['p_placebo']:.3f}")
    return res


# ============================================================
# Step 6. 결과 그림 + 요약 엑셀
#   그림 1: 49개 산업 방향 보정 평균 CAR [-1,+1] (전체 표본) + 95% 신뢰구간
#   그림 2: 관심 산업 12개 — 전체 vs 오염 제외 비교 (두 구간)
#   그림 3: 이벤트 × 관심 산업 CAR 히트맵 [-1,+1] (방향 보정 전)
# ============================================================
def label(k):
    return f"{KOR[k]} ({k})" if k in KOR else k


def fig1_all_industries(res):
    w = REPORT_WINDOWS[0]
    d = res[(res["window"] == w) & (res["sample"] == "전체") & (res["group"] == "통합(방향 보정)")].dropna(subset=["mean"])
    d = d.sort_values("mean")
    y = np.arange(len(d))
    sig = (d["p_bmp"] < 0.05).to_numpy()
    fig, ax = plt.subplots(figsize=(8, 0.24 * len(d) + 1.8))
    ax.hlines(y, d["lo"], d["hi"], color=np.where(sig, "#2a78d6", "#b8c4d6"), linewidth=1.6)
    ax.scatter(d["mean"], y, s=26, color=np.where(sig, "#2a78d6", "#8b99ad"), zorder=3)
    ax.axvline(0, color="#8b99ad", linestyle="--", linewidth=1)
    ax.set_yticks(y); ax.set_yticklabels([label(k) for k in d["ind"]], fontsize=8)
    ax.set_xlabel(f"방향 보정 평균 CAR {w} (%) · 95% 신뢰구간")
    ax.set_title(f"제도화 이벤트에 대한 49개 산업 반응 (파랑 = BMP p<0.05, N={int(d['N'].max())})", loc="left", fontsize=11)
    ax.grid(axis="x", color="#e5e9ef")
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    plt.tight_layout(); plt.savefig(os.path.join(OUT, "fig1_all_industries.png"), dpi=200); plt.close(fig)


def fig2_focus_compare(res, ev):
    color, mark = {"전체": "#8b99ad", "오염 제외": "#2a78d6"}, {"전체": "o", "오염 제외": "s"}
    fig, axes = plt.subplots(1, len(REPORT_WINDOWS), figsize=(6.5 * len(REPORT_WINDOWS), 6.5), sharey=True)
    yb = np.arange(len(FOCUS))[::-1]
    for ax, w in zip(np.atleast_1d(axes), REPORT_WINDOWS):
        for i, s in enumerate(["전체", "오염 제외"]):
            d = res[(res["window"] == w) & (res["sample"] == s) & (res["group"] == "통합(방향 보정)")].set_index("ind").reindex(FOCUS)
            y = yb + (0.15 if i == 0 else -0.15)
            n = len(ev) if s == "전체" else int(ev[f"clean_{w}"].sum())
            ax.hlines(y, d["lo"], d["hi"], color=color[s], linewidth=2)
            ax.plot(d["mean"], y, mark[s], color=color[s], markersize=7, markeredgecolor="white", label=f"{s} (N={n})")
        ax.axvline(0, color="#8b99ad", linestyle="--", linewidth=1)
        ax.set_yticks(yb); ax.set_yticklabels([label(k) for k in FOCUS])
        ax.set_title(f"구간 {w}"); ax.set_xlabel("방향 보정 평균 CAR (%) · 95% 신뢰구간")
        ax.grid(axis="x", color="#e5e9ef")
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2, frameon=False)
    fig.suptitle("관심 산업의 반응: 전체 vs FOMC·CPI 오염 제외")
    plt.tight_layout(); plt.savefig(os.path.join(OUT, "fig2_focus_full_vs_clean.png"), dpi=200, bbox_inches="tight"); plt.close(fig)


def fig3_heatmap(car, ev):
    w = REPORT_WINDOWS[0]
    m = car[car["window"] == w].pivot_table(index="event_id", columns="ind", values="CAR").reindex(columns=FOCUS)
    m = m.reindex(ev.sort_values("t0")["event_id"])
    lim = np.nanpercentile(np.abs(m.to_numpy()), 95)
    fig, ax = plt.subplots(figsize=(11, 0.34 * len(m) + 2))
    im = ax.imshow(m.to_numpy(), cmap="RdBu_r", vmin=-lim, vmax=lim, aspect="auto")
    names = ev.set_index("event_id")
    ax.set_yticks(range(len(m)))
    ax.set_yticklabels([f"{i} {'+' if names.loc[i, 'direction'] == 1 else '-'} {names.loc[i, 'title'][:20]}" for i in m.index], fontsize=8)
    ax.set_xticks(range(len(FOCUS))); ax.set_xticklabels([label(k) for k in FOCUS], rotation=40, ha="right", fontsize=8)
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            v = m.iat[i, j]
            if pd.notna(v):
                ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=6.5, color="white" if abs(v) > lim * 0.6 else "#333")
    fig.colorbar(im, ax=ax, label=f"CAR {w} (%, 방향 보정 전)")
    ax.set_title(f"이벤트별 관심 산업 반응 {w} (빨강 = 상승, 파랑 = 하락, 이벤트 옆 +/- = 제도 진전/후퇴)", loc="left", fontsize=10)
    plt.tight_layout(); plt.savefig(os.path.join(OUT, "fig3_event_heatmap.png"), dpi=200); plt.close(fig)


def step6_output(res, car, ev):
    fig1_all_industries(res)
    fig2_focus_compare(res, ev)
    fig3_heatmap(car, ev)
    with pd.ExcelWriter(os.path.join(OUT, "industry_results.xlsx"), engine="openpyxl") as xw:
        for w in REPORT_WINDOWS:
            a = res[(res["window"] == w) & (res["group"] == "통합(방향 보정)")]
            t = a.pivot_table(index="ind", columns="sample", values=["mean", "p_bmp", "p_placebo", "q_fdr", "N"])
            t.columns = [f"{s} {c}" for c, s in t.columns]
            t.insert(0, "산업", [label(k) for k in t.index])
            t.sort_values("전체 p_bmp").round(4).to_excel(xw, sheet_name="요약 " + w.strip("[]").replace(",", " ~ "))
        res.round(4).to_excel(xw, sheet_name="상세 결과", index=False)
        ev.to_excel(xw, sheet_name="이벤트·오염", index=False)
    print(f"[Step 6] 저장: results/industry_results.xlsx, 그림 3개 (results/fig*.png)")


# ============================================================
# 실행
# ============================================================
def main(refresh=False):
    for d in (DATA, OUT):
        os.makedirs(d, exist_ok=True)
    ind, mkt = step1_data(refresh)
    ev = step2_events(ind.index)
    ar, car = step3_car(ind, mkt, ev)
    ev = step4_overlap(ev, ind.index)
    res = step5_tests(car, ev, ind, mkt)
    step6_output(res, car, ev)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Fama-French 49 산업 이벤트 스터디")
    ap.add_argument("--refresh", action="store_true", help="French 라이브러리에서 새로 다운로드")
    main(ap.parse_args().refresh)
