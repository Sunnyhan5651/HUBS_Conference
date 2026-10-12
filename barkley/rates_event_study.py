"""
미국 크립토 제도화 이벤트 → 미국 금리 반응 이벤트 스터디 (Step 1~6 통합본)

실행:  python rates_event_study.py            # data/에 원본이 있으면 재사용, 없으면 FRED에서 다운로드
       python rates_event_study.py --refresh  # FRED에서 새로 다운로드

입력:  최종_이벤트_리스트.xlsx (같은 폴더)
출력:  data/ 아래 CSV, 결과 엑셀(step6_결과_전체vs오염제외.xlsx), 그림 3개(PNG)
"""
import argparse
import glob
import os
import time
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch
from scipy import stats

# ============================================================
# 설정
# ============================================================
BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
EVENT_FILE = os.path.join(BASE, "최종_이벤트_리스트.xlsx")

START = "2016-01-01"                 # 가장 이른 이벤트(2017-12)보다 1년 이상 앞 → 추정 구간 확보
SERIES = {
    "DGS1MO": "1개월", "DGS3MO": "3개월", "SOFR": "SOFR", "DGS2": "2년", "DGS5": "5년",
    "DGS10": "10년", "DGS30": "30년", "T10Y2Y": "10Y-2Y", "T10Y3M": "10Y-3M",
}
VARS = list(SERIES) + ["BILL_SOFR"]
NAMES = {**SERIES, "BILL_SOFR": "3M-SOFR"}

EST_START, EST_END = -125, -6        # 추정 구간(평소 움직임): 이벤트 구간 직전에서 끊음, 120거래일
W = 5                                # 이벤트 구간 [-5, +5]
WINDOWS = {"[-5,+5]": (-5, 5), "[-5,-1]": (-5, -1), "[0,+5]": (0, 5), "[-1,+1]": (-1, 1), "[0,0]": (0, 0)}
REPORT_WINDOWS = ["[-5,+5]", "[-1,+1]"]   # 표본 비교에 쓰는 구간 (첫 번째가 메인)
CONTAM_RULE = "FOMC·CPI"             # 오염 기준: "FOMC·CPI"(구간 안 FOMC·CPI 여부) 또는 "엑셀"(엑셀 '매크로 일정 겹침' 열)
N_SIM = 2000                         # placebo 반복 횟수
GROUPS = ["통합(방향 보정)", "긍정(+1)", "부정(-1)"]
KEY_VAR = "BILL_SOFR"                # 그림 3에서 이벤트별로 볼 변수

COLOR = {"전체": "#2a78d6", "오염 제외": "#eb6834"}
MARK = {"전체": "o", "오염 제외": "s"}
plt.rcParams["font.family"] = "Malgun Gothic"     # Mac: "AppleGothic"
plt.rcParams["axes.unicode_minus"] = False
warnings.filterwarnings("ignore", message="Mean of empty slice")   # SOFR 시작 전 날짜의 placebo 빈칸

# FOMC 결정일 (2020/3 긴급 회의 2회 포함)
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
# CPI 발표일 (BLS 공식 기록, 2025 셧다운: 10월 발표 10/24, 11월 발표 없음)
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
# Step 1. FRED에서 미국 금리 다운로드
#   - API 키 없이 CSV 다운로드 주소로 받음, 원본은 받은 날짜를 붙여 그대로 저장
# ============================================================
def get_fred(series_id, start=START):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start}"
    df = pd.read_csv(url, index_col=0, parse_dates=True, na_values=".")   # FRED는 결측을 "."으로 표시
    s = df.iloc[:, 0]
    s.name, s.index.name = series_id, "date"
    return s


def step1_download(refresh=False):
    files = sorted(glob.glob(os.path.join(DATA, "us_rates_raw_*.csv")))
    if files and not refresh:
        print(f"[Step 1] 기존 원본 사용: {os.path.basename(files[-1])}")
        return pd.read_csv(files[-1], index_col=0, parse_dates=True)

    collected = []
    for code in SERIES:
        try:
            collected.append(get_fred(code))
            print(f"[Step 1] 성공: {code}")
        except Exception as e:
            print(f"[Step 1] 실패: {code} → {e}")
        time.sleep(1)                                   # 서버에 연속 요청하지 않도록
    rates = pd.concat(collected, axis=1)
    rates.to_csv(os.path.join(DATA, f"us_rates_raw_{pd.Timestamp.today():%Y%m%d}.csv"))
    return rates


# ============================================================
# Step 2. 데이터 정리
#   - 모든 열이 빈 날(휴장일)만 삭제, 나머지 빈칸은 채우지 않음 (채우면 '변화 0'이라는 가짜 데이터가 생김)
#   - 3개월 국채 - SOFR 스프레드(bp): 연준 기대를 상쇄하고 '단기 국채만의 수요'를 봄
#   - 금리 수준 → 하루 bp 변화
# ============================================================
def step2_clean(rates):
    rates = rates[~rates.isna().all(axis=1)].copy()
    rates["BILL_SOFR"] = (rates["DGS3MO"] - rates["SOFR"]) * 100

    chg = rates[list(SERIES)].diff() * 100              # % → bp
    chg["BILL_SOFR"] = rates["BILL_SOFR"].diff()        # 이미 bp
    chg = chg.iloc[1:]

    rates.to_csv(os.path.join(DATA, "us_rates_level.csv"))
    chg.to_csv(os.path.join(DATA, "us_rates_change_bp.csv"))
    print(f"[Step 2] 거래일 {len(chg)}일, 변수 {chg.shape[1]}개")
    return chg


# ============================================================
# Step 3. 이벤트 날짜를 거래일(t0)에 맞추기
#   - 엑셀의 '미국 주식 t0' = 장 마감 후·주말 발표를 이미 다음 거래일로 옮긴 날짜
#   - 그날이 미국 공휴일이면 searchsorted가 다음 첫 거래일로 옮김
#   - t0_pos(거래일 위치 번호)로 τ = -5 ~ +5를 계산
# ============================================================
def step3_align(chg):
    raw = pd.read_excel(EVENT_FILE, sheet_name="이벤트 리스트")
    dir_col = [c for c in raw.columns if "방향" in c][0]
    ev = raw[["이벤트 ID", "표본", "미국 주식 t0", "이벤트", "카테고리", dir_col, "클러스터", "매크로 일정 겹침"]].rename(columns={
        "이벤트 ID": "event_id", "표본": "sample", "미국 주식 t0": "t0_list", "이벤트": "title",
        "카테고리": "category", dir_col: "direction", "클러스터": "cluster", "매크로 일정 겹침": "macro_overlap_excel",
    })
    ev["t0_list"] = pd.to_datetime(ev["t0_list"])
    ev["t0_pos"] = chg.index.searchsorted(ev["t0_list"])
    ev["t0"] = chg.index[ev["t0_pos"]]
    ev["shifted"] = ev["t0"] != ev["t0_list"]
    ev = ev.sort_values("t0_pos").reset_index(drop=True)
    ev["gap_prev"] = ev["t0_pos"].diff()                # 5거래일 이내면 이벤트끼리 구간이 겹침

    ev.to_csv(os.path.join(DATA, "events_aligned.csv"), index=False)
    print(f"[Step 3] 이벤트 {len(ev)}개, 공휴일로 옮겨진 이벤트 {ev['shifted'].sum()}개, "
          f"5거래일 이내 인접 쌍 {(ev['gap_prev'] <= 5).sum()}개")
    return ev


# ============================================================
# Step 4. AR·CAR 계산 (Main 표본)
#   - AR = 그날 실제 변화 - 추정 구간 하루 평균 변화 (평균 조정 모형)
#   - CAR = 구간 동안 AR의 합
# ============================================================
def est_stats(chg, t0_pos, var):
    s = chg[var].iloc[max(0, t0_pos + EST_START): t0_pos + EST_END + 1].dropna()
    if len(s) < 60:                                     # SOFR 시작(2018/4) 전처럼 관측치가 부족하면 계산 안 함
        return np.nan, np.nan
    return s.mean(), s.std()


def step4_car(chg, main):
    rows = []
    for _, e in main.iterrows():
        for var in VARS:
            mu, sd = est_stats(chg, e["t0_pos"], var)
            for tau in range(-W, W + 1):
                pos = e["t0_pos"] + tau
                if pos >= len(chg):
                    continue
                actual = chg[var].iloc[pos]
                rows.append({"event_id": e["event_id"], "var": var, "tau": tau,
                             "actual": actual, "normal": mu, "AR": actual - mu, "est_sd": sd})
    ar = pd.DataFrame(rows)

    cars = []
    for wname, (a, b) in WINDOWS.items():
        s = (ar[(ar["tau"] >= a) & (ar["tau"] <= b)]
             .groupby(["event_id", "var"])["AR"].sum(min_count=1).rename("CAR").reset_index())
        s["window"] = wname
        cars.append(s)
    car = pd.concat(cars).merge(main[["event_id", "title", "direction"]], on="event_id")

    ar.to_csv(os.path.join(DATA, "main_AR.csv"), index=False)
    car.to_csv(os.path.join(DATA, "main_CAR.csv"), index=False)
    print(f"[Step 4] Main {main['event_id'].nunique()}개 이벤트 AR·CAR 계산 완료")
    return ar, car


# ============================================================
# Step 5. 오염 판정 + 통계 검정
#   - 오염: 보는 구간 안에 FOMC 결정일 또는 CPI 발표일이 있으면 오염
#   - 방향 보정: 부정(-1) 이벤트의 CAR에 -1을 곱해 긍정 이벤트와 합침
#   - BMP(메인): SCAR = CAR / (추정 구간 표준편차 × √구간 일수) 로 t검정
#   - 부호 검정, placebo(가짜 이벤트 N_SIM회), BH-FDR(변수 10개 동시 검정 보정)
# ============================================================
def overlaps(dates, t0_pos, a, b):
    lo, hi = dates[max(0, t0_pos + a)], dates[min(len(dates) - 1, t0_pos + b)]
    hits = [f"FOMC {d:%m/%d}" for d in FOMC if lo <= d <= hi] + [f"CPI {d:%m/%d}" for d in CPI if lo <= d <= hi]
    return ", ".join(hits)


def bh_qvalues(p):
    p = np.asarray(p, dtype=float)
    n, order = len(p), np.argsort(p)
    ranked = np.minimum.accumulate((p[order] * n / np.arange(1, n + 1))[::-1])[::-1]
    q = np.empty(n)
    q[order] = np.minimum(ranked, 1)
    return q


class Tester:
    """표본(이벤트 ID 목록)·구간·그룹을 넣으면 변수별 검정 결과표를 돌려줌"""

    def __init__(self, chg, ev, main, ar, car):
        self.chg, self.main, self.ar, self.car = chg, main, ar, car
        excluded = set()                                # 진짜 이벤트(49개) 주변 ±10거래일은 가짜 이벤트 후보에서 제외
        for p in ev["t0_pos"]:
            excluded.update(range(p - 10, p + 11))
        self.cand = np.array([i for i in range(130, len(chg) - 6) if i not in excluded])
        self.est_mean = chg.rolling(120, min_periods=60).mean().shift(6)       # τ = -125 ~ -6 평균
        self.placebo = {w: self._placebo_array(w) for w in REPORT_WINDOWS}

    def _placebo_array(self, window):
        """모든 날짜에 대해 '그날이 t0라면' CAR을 미리 계산"""
        a, b = WINDOWS[window]
        n = b - a + 1
        s = self.chg.rolling(n, min_periods=max(1, n - 3)).sum().shift(-b)
        c = self.chg.notna().rolling(n).sum().shift(-b)
        return (s - c * self.est_mean).iloc[self.cand][VARS].to_numpy()

    def _car_with_scar(self, window):
        a, b = WINDOWS[window]
        L = (self.ar[(self.ar["tau"] >= a) & (self.ar["tau"] <= b)]
             .groupby(["event_id", "var"]).agg(L=("AR", "count"), est_sd=("est_sd", "first")).reset_index())
        d = self.car[self.car["window"] == window].merge(L, on=["event_id", "var"])
        d["SCAR"] = d["CAR"] / (d["est_sd"] * np.sqrt(d["L"]))
        return d

    def run(self, ids, window, group="통합(방향 보정)", seed=42):
        d_all = self._car_with_scar(window)
        d_all = d_all[d_all["event_id"].isin(ids)].copy()
        if group == "긍정(+1)":
            d_all = d_all[d_all["direction"] == 1].copy(); d_all["sgn"] = 1
        elif group == "부정(-1)":
            d_all = d_all[d_all["direction"] == -1].copy(); d_all["sgn"] = 1
        else:
            d_all = d_all[d_all["direction"] != 0].copy(); d_all["sgn"] = d_all["direction"]

        dirs = self.main.set_index("event_id").loc[d_all["event_id"].unique(), "direction"].to_numpy()
        if group != "통합(방향 보정)":
            dirs = np.ones(len(dirs))
        rng = np.random.default_rng(seed)
        idx = rng.integers(0, len(self.cand), size=(N_SIM, len(dirs)))
        sims = np.nanmean(self.placebo[window][idx] * dirs[None, :, None], axis=1) if len(dirs) else None

        rows = []
        for j, var in enumerate(VARS):
            d = d_all[d_all["var"] == var].dropna(subset=["CAR"])
            x, z = (d["CAR"] * d["sgn"]).to_numpy(), (d["SCAR"] * d["sgn"]).to_numpy()
            n = len(x)
            if n >= 3:
                se, tc = x.std(ddof=1) / np.sqrt(n), stats.t.ppf(0.975, n - 1)
                p_bmp = stats.ttest_1samp(z, 0).pvalue
                nz = x[x != 0]
                p_sign = stats.binomtest(int((nz > 0).sum()), len(nz), 0.5).pvalue
                p_pl = np.mean(np.abs(sims[:, j]) >= abs(x.mean()))
                lo, hi = x.mean() - tc * se, x.mean() + tc * se
            else:
                p_bmp = p_sign = p_pl = lo = hi = np.nan
            rows.append({"변수": NAMES[var], "var": var, "N": n, "평균 CAR(bp)": x.mean() if n else np.nan,
                         "95% 하한": lo, "95% 상한": hi, "p (BMP)": p_bmp, "p (부호)": p_sign, "p (placebo)": p_pl})
        out = pd.DataFrame(rows)
        ok = out["p (BMP)"].notna()
        out["q (FDR)"] = np.nan
        out.loc[ok, "q (FDR)"] = bh_qvalues(out.loc[ok, "p (BMP)"])
        return out


def step5_overlap(chg, main):
    main = main.copy()
    main["overlap_5"] = [overlaps(chg.index, p, -5, 5) for p in main["t0_pos"]]
    main["overlap_1"] = [overlaps(chg.index, p, -1, 1) for p in main["t0_pos"]]
    main["clean_5"] = main["overlap_5"] == ""
    main["clean_1"] = main["overlap_1"] == ""
    main["clean_excel"] = main["macro_overlap_excel"].fillna("—").str.strip() == "—"
    main[["event_id", "title", "direction", "overlap_1", "overlap_5", "clean_1", "clean_5"]].to_csv(
        os.path.join(DATA, "step5_overlap_check.csv"), index=False, encoding="utf-8-sig")
    print(f"[Step 5] 오염 제외 표본: [-5,+5] {main['clean_5'].sum()}개, [-1,+1] {main['clean_1'].sum()}개 / {len(main)}개")
    return main


# ============================================================
# Step 6. 전체 vs 오염 제외 표본 비교 + 결과 저장
# ============================================================
def sample_ids(main, window, which):
    if which == "전체":
        return list(main["event_id"])
    col = "clean_excel" if CONTAM_RULE == "엑셀" else ("clean_5" if window == "[-5,+5]" else "clean_1")
    return list(main.loc[main[col], "event_id"])


def stars(p):
    if pd.isna(p):
        return ""
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


def compare_table(results, window, group):
    A, B = results[(window, "전체", group)], results[(window, "오염 제외", group)]
    t = pd.DataFrame({"변수": A["변수"]})
    for lab, R in [("전체", A), ("오염 제외", B)]:
        t[f"{lab} N"] = R["N"]
        t[f"{lab} 평균(bp)"] = R["평균 CAR(bp)"].round(1).astype(str) + R["p (BMP)"].apply(stars)
        t[f"{lab} p(BMP)"] = R["p (BMP)"].round(3)
        t[f"{lab} p(placebo)"] = R["p (placebo)"].round(3)
        t[f"{lab} FDR"] = np.where(R["q (FDR)"] < 0.05, "O", "")
    t["평균 차이(제외-전체)"] = (B["평균 CAR(bp)"] - A["평균 CAR(bp)"]).round(1)
    return t


def interpret(results, window, group="통합(방향 보정)", alpha=0.05):
    """비교 규칙: 둘 다 유의 → 견고 / 전체만 유의 → 표본 축소 또는 착시 / 제외만 유의 → 가려진 효과 / 둘 다 아님 → 전이 없음"""
    A, B = results[(window, "전체", group)], results[(window, "오염 제외", group)]
    lines = []
    for i, var in enumerate(VARS):
        a, b = A.iloc[i], B.iloc[i]
        ma, mb = a["평균 CAR(bp)"], b["평균 CAR(bp)"]
        sa, sb = a["p (BMP)"] < alpha, b["p (BMP)"] < alpha
        same = np.sign(ma) == np.sign(mb)
        if b["N"] < 5:
            v = f"오염 제외 {int(b['N'])}개라 검정 불가, 방향 {'같음' if same else '반대'} ({ma:.1f} → {mb:.1f}bp)"
        elif sa and sb and same:
            v = f"두 표본 모두 유의 → 견고 ({ma:.1f} / {mb:.1f}bp)"
        elif sa and not sb:
            v = (f"전체만 유의, 방향·크기 유지 → 표본 축소 탓 가능 ({ma:.1f} → {mb:.1f}bp)" if same and abs(mb) >= 0.7 * abs(ma)
                 else f"전체만 유의, 효과 약화 → 매크로 착시 가능 ({ma:.1f} → {mb:.1f}bp)")
        elif not sa and sb:
            v = f"오염 제외만 유의 → 매크로가 효과를 가렸을 가능성 ({ma:.1f} → {mb:.1f}bp)"
        else:
            v = f"두 표본 모두 비유의 → 전이 없음 ({ma:.1f} / {mb:.1f}bp)"
        lines.append(f"{NAMES[var]}: {v}")
    return lines


def plot_ci(results, main):
    fig, axes = plt.subplots(1, len(REPORT_WINDOWS), figsize=(6.5 * len(REPORT_WINDOWS), 6), sharey=True)
    ypos = np.arange(len(VARS))[::-1]
    for ax, w in zip(np.atleast_1d(axes), REPORT_WINDOWS):
        for k, s in enumerate(["전체", "오염 제외"]):
            R = results[(w, s, "통합(방향 보정)")]
            y = ypos + (0.15 if k == 0 else -0.15)
            ax.hlines(y, R["95% 하한"], R["95% 상한"], color=COLOR[s], linewidth=2)
            ax.plot(R["평균 CAR(bp)"], y, MARK[s], color=COLOR[s], markersize=8, markeredgecolor="white",
                    label=f"{s} (N={len(sample_ids(main, w, s))})")
        ax.axvline(0, color="#8b99ad", linestyle="--", linewidth=1)
        ax.set_yticks(ypos); ax.set_yticklabels([NAMES[v] for v in VARS])
        ax.set_title(f"구간 {w}"); ax.set_xlabel("평균 CAR (bp, 방향 보정) · 95% 신뢰구간")
        ax.grid(axis="x", color="#e5e9ef")
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=2, frameon=False)
    fig.suptitle(f"제도화 이벤트의 미국 금리 반응: 전체 vs 오염 제외 (오염 기준: {CONTAM_RULE})")
    plt.tight_layout()
    plt.savefig(os.path.join(DATA, "fig6_1_ci_compare.png"), dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_caar(ar, main):
    w0 = REPORT_WINDOWS[0]

    def caar_path(ids):
        d = ar[ar["event_id"].isin(ids)].merge(main[["event_id", "direction"]], on="event_id")
        d = d[d["direction"] != 0]
        d["AR_adj"] = d["AR"] * d["direction"]
        return d.groupby(["var", "tau"])["AR_adj"].mean().groupby(level=0).cumsum()

    paths = {s: caar_path(sample_ids(main, w0, s)) for s in ["전체", "오염 제외"]}
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), sharex=True)
    for ax, var in zip(axes, ["DGS2", "BILL_SOFR"]):
        for s in ["전체", "오염 제외"]:
            p = paths[s].loc[var]
            ax.plot(p.index, p.values, marker=MARK[s], color=COLOR[s], linewidth=2,
                    label=f"{s} (N={len(sample_ids(main, w0, s))})")
        ax.axvline(0, color="#8b99ad", linestyle="--", linewidth=1); ax.axhline(0, color="#8b99ad", linewidth=0.8)
        ax.set_title(f"{NAMES[var]} · 방향 보정 CAAR"); ax.set_xlabel("τ (거래일)"); ax.grid(color="#e5e9ef")
    axes[0].set_ylabel("누적 비정상 변화 (bp)"); axes[0].legend(frameon=False)
    plt.tight_layout()
    plt.savefig(os.path.join(DATA, "fig6_2_caar_compare.png"), dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_event_bars(tester, main):
    w0 = REPORT_WINDOWS[0]
    d = tester._car_with_scar(w0)
    d = d[(d["var"] == KEY_VAR) & (d["direction"] != 0)].copy()
    d["adj"] = d["CAR"] * d["direction"]
    d["clean"] = d["event_id"].isin(set(sample_ids(main, w0, "오염 제외")))
    d = d.sort_values("adj")
    d["label"] = d["event_id"] + " " + d["title"].str.slice(0, 22)

    fig, ax = plt.subplots(figsize=(9, 0.32 * len(d) + 1.5))
    ax.barh(d["label"], d["adj"], color=np.where(d["clean"], COLOR["오염 제외"], "#b8c4d6"), height=0.7)
    ax.axvline(0, color="#8b99ad", linewidth=1)
    ax.set_xlabel(f"{NAMES[KEY_VAR]} CAR {w0} (bp, 방향 보정)"); ax.set_title(f"이벤트별 반응 · {NAMES[KEY_VAR]}")
    ax.legend(handles=[Patch(color=COLOR["오염 제외"], label="오염 제외 표본에 포함"),
                       Patch(color="#b8c4d6", label="매크로 일정과 겹쳐 제외")], frameon=False, loc="lower right")
    ax.grid(axis="x", color="#e5e9ef")
    plt.tight_layout()
    plt.savefig(os.path.join(DATA, "fig6_3_event_bars.png"), dpi=200, bbox_inches="tight")
    plt.close(fig)


def step6_compare(tester, main, ar, car):
    results = {(w, s, g): tester.run(sample_ids(main, w, s), w, g)
               for w in REPORT_WINDOWS for s in ["전체", "오염 제외"] for g in GROUPS}

    for w in REPORT_WINDOWS:
        print(f"\n[Step 6] 통합(방향 보정) · {w}")
        for line in interpret(results, w):
            print("   ", line)

    excl = []
    for w in REPORT_WINDOWS:
        keep = set(sample_ids(main, w, "오염 제외"))
        col = "macro_overlap_excel" if CONTAM_RULE == "엑셀" else ("overlap_5" if w == "[-5,+5]" else "overlap_1")
        for _, e in main[~main["event_id"].isin(keep)].iterrows():
            excl.append({"구간": w, "이벤트 ID": e["event_id"], "이벤트": e["title"],
                         "방향": e["direction"], "제외 사유 (겹친 일정)": e[col]})

    out = os.path.join(DATA, "step6_결과_전체vs오염제외.xlsx")
    with pd.ExcelWriter(out, engine="openpyxl") as xw:
        row = 0
        for w in REPORT_WINDOWS:
            t = compare_table(results, w, "통합(방향 보정)")
            pd.DataFrame({f"■ 통합(방향 보정) · {w} · 오염 기준: {CONTAM_RULE}": []}).to_excel(xw, sheet_name="요약 비교", startrow=row, index=False)
            t.to_excel(xw, sheet_name="요약 비교", startrow=row + 1, index=False)
            row += len(t) + 3
            interp = pd.DataFrame({"자동 해석": interpret(results, w)})
            interp.to_excel(xw, sheet_name="요약 비교", startrow=row, index=False)
            row += len(interp) + 3
        detail = []
        for (w, s, g), R in results.items():
            R = R.copy(); R.insert(0, "그룹", g); R.insert(0, "표본", s); R.insert(0, "구간", w)
            detail.append(R.drop(columns="var"))
        pd.concat(detail).round(4).to_excel(xw, sheet_name="상세 결과", index=False)
        pd.DataFrame(excl).to_excel(xw, sheet_name="제외 이벤트", index=False)
        (car[car["window"].isin(REPORT_WINDOWS)]
         .pivot_table(index=["window", "event_id", "title", "direction"], columns="var", values="CAR")[VARS]
         .rename(columns=NAMES).round(2).reset_index()
         .to_excel(xw, sheet_name="이벤트별 CAR", index=False))

    plot_ci(results, main)
    plot_caar(ar, main)
    plot_event_bars(tester, main)
    print(f"\n[Step 6] 저장: {out}, 그림 3개 (data/fig6_*.png)")
    return results


# ============================================================
# 실행
# ============================================================
def main(refresh=False):
    os.makedirs(DATA, exist_ok=True)
    rates = step1_download(refresh)
    chg = step2_clean(rates)
    ev = step3_align(chg)
    main_ev = ev[ev["sample"] == "Main"].reset_index(drop=True)
    ar, car = step4_car(chg, main_ev)
    main_ev = step5_overlap(chg, main_ev)
    tester = Tester(chg, ev, main_ev, ar, car)
    return step6_compare(tester, main_ev, ar, car)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="미국 금리 이벤트 스터디 (Step 1~6)")
    parser.add_argument("--refresh", action="store_true", help="FRED에서 데이터를 새로 다운로드")
    main(refresh=parser.parse_args().refresh)
