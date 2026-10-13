"""
Korea_variable_backtest.py
────────────────────────────────────────────────────────────────
국내 변수 이벤트 드리븐 백테스트
: 디지털 자산 제도화 이벤트 → KOSPI · KOSDAQ · 국고채 3년 · 10년 충격 분석

데이터:
  KOSPI / KOSDAQ : FinanceDataReader (KRX 공식 데이터 기반 GitHub 캐시, 결측치 없음)
  국고채 3년·10년 : ECOS API 817Y002 (한국은행 ECOS_API_KEY)

이벤트 t0 : 한국 주식 t0 (한국 시장 첫 반영일)
이벤트 창  : [-5, +5] (메인) / [-1, +1] (보조)
추정 창    : 이벤트 전 120 거래일
오염 기준  : FOMC·CPI가 ±2 거래일 내
단위       : 주가지수 → 일수익률(%), 국고채 → 일변화(bp)
────────────────────────────────────────────────────────────────
"""

import os, sys, json, re, unicodedata, warnings
import urllib.request
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.font_manager as fm
from scipy import stats
import FinanceDataReader as fdr

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from config import ECOS_API_KEY

warnings.filterwarnings("ignore")

# ── 한글 폰트
def _set_korean_font():
    candidates = ["AppleGothic", "Apple SD Gothic Neo", "NanumGothic", "Malgun Gothic"]
    available = {f.name for f in fm.fontManager.ttflist}
    for name in candidates:
        if name in available:
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False

_set_korean_font()

# ── 한글 너비 보정 테이블 출력
def _dw(s):
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in str(s))

def _pad(s, width, align="right"):
    s = str(s); pad = width - _dw(s)
    return s + " " * pad if align == "left" else " " * pad + s

def print_table(df, title=""):
    cols = list(df.columns)
    rows = [[str(df.iloc[i, j]) for j in range(len(cols))] for i in range(len(df))]
    col_widths = [max(_dw(c), max((_dw(r[j]) for r in rows), default=0)) for j, c in enumerate(cols)]
    sep = "─" * (sum(col_widths) + 3 * len(cols) + 1)
    if title:
        print(f"\n{sep}\n  {title}")
    print(sep)
    print("│ " + " │ ".join(_pad(c, col_widths[j], "left") for j, c in enumerate(cols)) + " │")
    print(sep)
    for row in rows:
        print("│ " + " │ ".join(_pad(v, col_widths[j]) for j, v in enumerate(row)) + " │")
    print(sep)

# ──────────────────────────────────────────────────────────────
# 0. 경로 및 설정
# ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
OUT_DIR  = os.path.join(BASE_DIR, "output")
os.makedirs(OUT_DIR, exist_ok=True)

EVENT_XLS = os.path.join(DATA_DIR, "이벤트 리스트 제안.xlsx")
START_STR = "20150101"
START_TS  = pd.Timestamp("2015-01-01")

# 분석 대상 자산 정의
ASSETS = {
    "KOSPI"   : {"label": "KOSPI",       "unit": "%",  "source": "fdr",  "code": "KS11"},
    "KOSDAQ"  : {"label": "KOSDAQ",      "unit": "%",  "source": "fdr",  "code": "KQ11"},
    "KTB_3Y"  : {"label": "국고채 3년",  "unit": "bp", "source": "ecos", "code": "010200000", "cycle": "D"},
    "KTB_10Y" : {"label": "국고채 10년", "unit": "bp", "source": "ecos", "code": "010210000", "cycle": "D"},
}
EQUITY_ASSETS = {"KOSPI", "KOSDAQ"}   # 방향 조정 적용 대상

# ──────────────────────────────────────────────────────────────
# 1. 데이터 로드
# ──────────────────────────────────────────────────────────────
def get_fdr(code, start="2015-01-01"):
    print(f"  FDR 로딩: {code} ({start}~)")
    df = fdr.DataReader(code, start)
    if df is None or df.empty:
        return pd.Series(dtype=float, name=code)
    s = df["Close"].copy()
    s.index = pd.to_datetime(s.index)
    s.index.name = "date"
    s.name = code
    return s.sort_index()

def get_ecos(stat_code, item_code, start="20150101", end="20261231", cycle="D"):
    url = (f"https://ecos.bok.or.kr/api/StatisticSearch/"
           f"{ECOS_API_KEY}/json/kr/1/10000/"
           f"{stat_code}/{cycle}/{start}/{end}/{item_code}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        rows = data.get("StatisticSearch", {}).get("row", [])
        if not rows:
            return pd.Series(dtype=float, name=item_code)
        s = pd.Series(
            {pd.Timestamp(row["TIME"]): float(row["DATA_VALUE"].replace(",", ""))
             for row in rows if row.get("DATA_VALUE") not in ("", None)},
            name=item_code,
        )
        s.index.name = "date"
        return s.sort_index()
    except Exception as e:
        print(f"    ECOS 로드 실패({item_code}): {e}")
        return pd.Series(dtype=float, name=item_code)

print("=" * 58)
print("국내 변수 데이터 로딩 중...")
print("=" * 58)

price_data = {}
for key, cfg in ASSETS.items():
    if cfg["source"] == "fdr":
        s = get_fdr(cfg["code"])
    else:
        cycle = cfg.get("cycle", "D")
        print(f"  ECOS 로딩: {cfg['label']} (817Y002 / {cfg['code']})")
        s = get_ecos("817Y002", cfg["code"], cycle=cycle)
    s = s.ffill().dropna()
    price_data[key] = s
    print(f"    {cfg['label']}: {len(s)}행  "
          f"({s.index[0].date()} ~ {s.index[-1].date()})  "
          f"최근값: {s.iloc[-1]:.2f}{cfg['unit'] if cfg['unit']=='%' else ''}")

# ──────────────────────────────────────────────────────────────
# 2. 이벤트 데이터 로드
# ──────────────────────────────────────────────────────────────
print("\n이벤트 데이터 로딩 중...")
ev_xl   = pd.read_excel(EVENT_XLS, sheet_name="이벤트 리스트")
ev_xl["한국 주식 t0"] = pd.to_datetime(ev_xl["한국 주식 t0"])
ev_xl["방향"]         = pd.to_numeric(ev_xl["방향(+1/0/−1)"], errors="coerce")
ev_main = ev_xl[ev_xl["표본"] == "Main"].copy().reset_index(drop=True)
print(f"  Main 표본: {len(ev_main)}건  (t0 기준: 한국 주식 t0)")

# ──────────────────────────────────────────────────────────────
# 3. 오염 판정
# ──────────────────────────────────────────────────────────────
STRICT = 2

def _fomc_cpi_offsets(macro_text):
    text = str(macro_text)
    offsets = []
    for m in re.finditer(r"(FOMC|CPI)[^(]*\(T([+\-−]?\d+)\)", text):
        try:
            offsets.append(int(m.group(2).replace("−", "-")))
        except ValueError:
            pass
    if re.search(r"(FOMC|CPI)[^\n]*당일", text):
        offsets.append(0)
    if re.search(r"(FOMC|CPI)[^\n]*\[", text):
        offsets.append(0)
    return offsets

def is_fomc_cpi_contaminated(macro_text, window=STRICT):
    return any(abs(o) <= window for o in _fomc_cpi_offsets(macro_text))

# ──────────────────────────────────────────────────────────────
# 4. 이벤트 스터디 (자산별 공통 함수)
# ──────────────────────────────────────────────────────────────
EST_LEN = 120

def compute_daily_changes(price_series, unit):
    """단위에 따라 일변화 계산: % return 또는 bp 변화"""
    if unit == "%":
        return price_series.ffill().pct_change().dropna() * 100
    else:  # bp
        return price_series.ffill().diff().dropna() * 100

def run_event_study(price_series, unit, event_df, date_col="한국 주식 t0", window=5):
    dy           = compute_daily_changes(price_series, unit)
    trading_days = dy.index
    ar_rows, meta_list = [], []

    for _, row in event_df.iterrows():
        event_date = pd.Timestamp(row[date_col])
        future = trading_days[trading_days >= event_date]
        if len(future) == 0:
            continue
        t0_date = future[0]
        t0_pos  = trading_days.get_loc(t0_date)

        est_end   = t0_pos - window - 1
        est_start = est_end - EST_LEN
        if est_start < 0 or est_end < 1:
            continue

        est_dy = dy.iloc[est_start:est_end].dropna()
        if len(est_dy) < 30:
            continue

        ev_start = t0_pos - window
        ev_end   = t0_pos + window + 1
        if ev_end > len(trading_days) or ev_start < 0:
            continue
        ev_dy = dy.iloc[ev_start:ev_end]
        if len(ev_dy) < 2 * window + 1:
            continue

        ar = ev_dy.values - est_dy.mean()
        macro_text = row.get("매크로 일정 겹침", "—")

        ar_rows.append(ar)
        meta_list.append({
            "event_id"    : row.get("이벤트 ID", ""),
            "event_date"  : event_date,
            "t0"          : t0_date,
            "direction"   : row.get("방향", np.nan),
            "category"    : row.get("카테고리", ""),
            "sigma_est"   : est_dy.std(ddof=1),
            "contaminated": is_fomc_cpi_contaminated(macro_text, STRICT),
        })

    cols      = list(range(-window, window + 1))
    ar_matrix = pd.DataFrame(ar_rows, columns=cols) if ar_rows else pd.DataFrame(columns=cols)
    return ar_matrix, meta_list

# ──────────────────────────────────────────────────────────────
# 5. 통계 검정
# ──────────────────────────────────────────────────────────────
def compute_stats(ar_matrix, meta, alpha=0.05):
    rows = {}
    n    = len(ar_matrix)
    caar = 0.0
    for day in ar_matrix.columns:
        ar_day = ar_matrix[day].values
        sigmas = np.array([m["sigma_est"] for m in meta])
        sigmas = np.where(sigmas < 1e-8, np.nan, sigmas)
        sar    = ar_day / sigmas
        sar_v  = sar[~np.isnan(sar)]

        caar += np.mean(ar_day)
        if len(sar_v) < 2:
            rows[day] = dict(AAR=np.nan, CAAR=caar, t_bmp=np.nan,
                             p_bmp=np.nan, sign_p=np.nan, sig=False)
            continue

        t_bmp  = np.mean(sar_v) / (np.std(sar_v, ddof=1) / np.sqrt(len(sar_v)))
        p_bmp  = 2 * (1 - stats.t.cdf(abs(t_bmp), df=len(sar_v) - 1))
        pos    = int(np.sum(ar_day > 0))
        sign_p = 2 * min(stats.binom.cdf(pos, n, 0.5),
                         1 - stats.binom.cdf(pos - 1, n, 0.5))
        rows[day] = dict(AAR=np.mean(ar_day), CAAR=caar,
                         t_bmp=t_bmp, p_bmp=p_bmp, sign_p=sign_p,
                         sig=p_bmp < alpha)

    return pd.DataFrame(rows).T

# ──────────────────────────────────────────────────────────────
# 6. Placebo 검정
# ──────────────────────────────────────────────────────────────
def placebo_test(ar_matrix, meta, price_series, unit, window=5, n_sim=2000):
    dy           = compute_daily_changes(price_series, unit)
    trading_days = dy.index
    actual_caar  = ar_matrix.values.sum(axis=1).mean()
    sim_caars    = []

    for _ in range(n_sim):
        valid_range = trading_days[EST_LEN + window + 1: -window - 1]
        if len(valid_range) == 0:
            break
        sim_cars = []
        for _ in range(len(meta)):
            idx    = np.random.randint(len(valid_range))
            t0_pos = trading_days.get_loc(valid_range[idx])
            est_end   = t0_pos - window - 1
            est_start = est_end - EST_LEN
            if est_start < 0:
                continue
            mu  = dy.iloc[est_start:est_end].mean()
            ev  = dy.iloc[t0_pos - window: t0_pos + window + 1]
            if len(ev) < 2 * window + 1:
                continue
            sim_cars.append((ev.values - mu).sum())
        if sim_cars:
            sim_caars.append(np.mean(sim_cars))

    sim_caars = np.array(sim_caars)
    p_upper   = np.mean(sim_caars >= actual_caar)
    p_lower   = np.mean(sim_caars <= actual_caar)
    return {
        "actual_caar": actual_caar,
        "sim_mean"   : np.mean(sim_caars),
        "sim_std"    : np.std(sim_caars),
        "p_placebo"  : 2 * min(p_upper, p_lower),
        "sim_caars"  : sim_caars,
    }

# ──────────────────────────────────────────────────────────────
# 7. 전체 실행
# ──────────────────────────────────────────────────────────────
print("\n" + "=" * 58)
print("이벤트 스터디 실행 중...")
print("=" * 58)

WINDOWS  = [5, 1]
DAYS     = {5: list(range(-5, 6)), 1: list(range(-1, 2))}
RESULTS  = {}   # key: (asset_key, window)
PLACEBO  = {}   # key: asset_key

for key, cfg in ASSETS.items():
    lbl    = cfg["label"]
    unit   = cfg["unit"]
    pseries = price_data[key]
    print(f"\n── {lbl} ({unit}) ─────────────────────────────")

    for WINDOW in WINDOWS:
        wlbl = f"[-{WINDOW},+{WINDOW}]"
        ar_mat, meta = run_event_study(pseries, unit, ev_main, window=WINDOW)
        if ar_mat.empty:
            print(f"  {wlbl}: 유효 이벤트 없음")
            continue
        st = compute_stats(ar_mat, meta)
        n_cont = sum(m["contaminated"] for m in meta)
        print(f"  {wlbl}  유효 {len(ar_mat)}건 (오염 {n_cont}건)  "
              f"CAAR: {ar_mat.values.sum(axis=1).mean():+.4f}{unit}  "
              f"t(t=0): {st.loc[0,'t_bmp']:+.3f}  p: {st.loc[0,'p_bmp']:.4f}")

        # 방향 조정 (주가지수만)
        dir_adj_res = None
        if key in EQUITY_ASSETS:
            dirs  = np.array([m["direction"] for m in meta])
            valid = ~(np.isnan(dirs) | (dirs == 0))
            if valid.sum() >= 5:
                ar_d  = ar_mat.loc[valid].copy()
                d_val = dirs[valid]
                ar_adj = ar_d.multiply(d_val, axis=0)
                st_adj = compute_stats(ar_adj, [m for m, v in zip(meta, valid) if v])
                dir_adj_res = {"ar": ar_adj, "stats": st_adj, "n": int(valid.sum())}
                print(f"         방향조정 {int(valid.sum())}건  "
                      f"Dir-Adj CAAR: {ar_adj.values.sum(axis=1).mean():+.4f}{unit}  "
                      f"t(t=0): {st_adj.loc[0,'t_bmp']:+.3f}  p: {st_adj.loc[0,'p_bmp']:.4f}")

        RESULTS[(key, WINDOW)] = {
            "ar": ar_mat, "meta": meta, "stats": st,
            "dir_adj": dir_adj_res, "label": lbl, "unit": unit, "wlbl": wlbl,
            # clean sample
            "ar_clean"  : ar_mat.iloc[[i for i,m in enumerate(meta) if not m["contaminated"]]].reset_index(drop=True),
            "meta_clean": [m for m in meta if not m["contaminated"]],
        }

    # Placebo ([-5,+5])
    if (key, 5) in RESULTS and not RESULTS[(key, 5)]["ar"].empty:
        print(f"  Placebo 실행 중...")
        pb = placebo_test(RESULTS[(key, 5)]["ar"], RESULTS[(key, 5)]["meta"],
                          pseries, unit, window=5)
        PLACEBO[key] = pb
        print(f"  Placebo p = {pb['p_placebo']:.4f}  "
              f"(실제 {pb['actual_caar']:+.4f}{unit} vs 랜덤 μ {pb['sim_mean']:+.4f}{unit})")

# ──────────────────────────────────────────────────────────────
# 8. 시각화
# ──────────────────────────────────────────────────────────────
print("\n차트 생성 중...")

COLORS = {
    "KOSPI"  : "#2471a3",
    "KOSDAQ" : "#1a9e6a",
    "KTB_3Y" : "#d35400",
    "KTB_10Y": "#8e44ad",
}

# ── 8-1. CAAR 4변수 개요 ([-5,+5], 2x2)
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle("국내 변수 CAAR — 디지털 자산 제도화 이벤트 (Main 22건, [-5,+5])",
             fontsize=13, fontweight="bold")
for ax, key in zip(axes.flat, ASSETS.keys()):
    cfg = ASSETS[key]
    lbl = cfg["label"]
    unit = cfg["unit"]
    color = COLORS[key]
    if (key, 5) not in RESULTS:
        ax.set_title(lbl); ax.text(0.5, 0.5, "데이터 없음", ha="center", va="center", transform=ax.transAxes)
        continue
    res    = RESULTS[(key, 5)]
    ar_mat = res["ar"]
    aar    = ar_mat.mean(axis=0)
    caar   = aar.cumsum()
    se     = ar_mat.std(axis=0, ddof=1) / np.sqrt(len(ar_mat))
    ax.plot(DAYS[5], caar.values, "-o", color=color, ms=4, lw=2,
            label=f"전체 (N={len(ar_mat)})")
    ax.fill_between(DAYS[5],
                    (caar - 1.96 * se.cumsum()).values,
                    (caar + 1.96 * se.cumsum()).values,
                    alpha=0.12, color=color)
    if res.get("dir_adj"):
        ar_d  = res["dir_adj"]["ar"]
        caar_d = ar_d.mean(axis=0).cumsum()
        ax.plot(DAYS[5], caar_d.values, "--", color=color, ms=3, lw=1.5,
                alpha=0.7, label=f"방향조정 (N={res['dir_adj']['n']})")
    ax.axhline(0, color="black", lw=0.8, linestyle="--")
    ax.axvline(0, color="gray",  lw=0.8, linestyle=":")
    ax.set_title(f"{lbl}  (단위: {unit})", fontsize=11)
    ax.set_xlabel("이벤트 상대일")
    ax.set_ylabel(f"CAAR ({unit})")
    ax.legend(fontsize=8)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(1))
    ax.grid(True, alpha=0.3)
plt.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "01_caar_4variables.png"), dpi=150)
plt.close()
print("  저장: 01_caar_4variables.png")

# ── 8-2. t=0 이벤트 당일 AAR 비교 (4변수 × 두 윈도우)
fig, axes = plt.subplots(1, 2, figsize=(13, 5))
fig.suptitle("이벤트 당일 (t=0) 평균 비정상 변화 — 4개 국내 변수", fontsize=12, fontweight="bold")
for ax, WINDOW in zip(axes, [5, 1]):
    labels, aars, errs, colors_list, sig_list = [], [], [], [], []
    for key, cfg in ASSETS.items():
        if (key, WINDOW) not in RESULTS:
            continue
        res = RESULTS[(key, WINDOW)]
        ar0  = res["ar"][0]
        se0  = res["ar"][0].std(ddof=1) / np.sqrt(len(res["ar"]))
        labels.append(cfg["label"])
        aars.append(ar0.mean())
        errs.append(1.96 * se0)
        colors_list.append(COLORS[key])
        sig_list.append(res["stats"].loc[0, "sig"])
    x = np.arange(len(labels))
    bars = ax.bar(x, aars, color=colors_list, alpha=0.75, edgecolor="white", width=0.6)
    ax.errorbar(x, aars, yerr=errs, fmt="none", color="black", capsize=5, lw=1.2)
    for i, (bar, sig) in enumerate(zip(bars, sig_list)):
        if sig:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + errs[i]*1.1,
                    "★", ha="center", va="bottom", fontsize=12, color="red")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_title(f"이벤트 창 [-{WINDOW},+{WINDOW}]")
    ax.set_ylabel("AAR (각 자산 단위)")
    ax.grid(True, alpha=0.3, axis="y")
    ax.text(0.02, 0.97, "★ = BMP p<0.05", transform=ax.transAxes,
            fontsize=8, va="top", color="red")
plt.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "02_t0_bar_comparison.png"), dpi=150)
plt.close()
print("  저장: 02_t0_bar_comparison.png")

# ── 8-3. KOSPI/KOSDAQ 긍정 vs 부정 CAAR
fig, axes = plt.subplots(1, 2, figsize=(13, 5))
fig.suptitle("KOSPI · KOSDAQ — 긍정 vs 부정 이벤트 CAAR ([-5,+5])", fontsize=12, fontweight="bold")
for ax, key in zip(axes, ["KOSPI", "KOSDAQ"]):
    if (key, 5) not in RESULTS:
        continue
    res  = RESULTS[(key, 5)]
    ar_mat = res["ar"]
    meta   = res["meta"]
    dirs   = np.array([m["direction"] for m in meta])
    for mask, color, lbl in [
        (dirs == 1,  "#27ae60", f"긍정(+1)  n={int((dirs==1).sum())}"),
        (dirs == -1, "#e74c3c", f"부정(−1)  n={int((dirs==-1).sum())}"),
    ]:
        if mask.sum() < 2:
            continue
        sub  = ar_mat.loc[mask]
        caar = sub.mean(axis=0).cumsum()
        se   = sub.std(axis=0, ddof=1) / np.sqrt(len(sub))
        ax.plot(DAYS[5], caar.values, lw=2, color=color, label=lbl)
        ax.fill_between(DAYS[5],
                        (caar - 1.96*se.cumsum()).values,
                        (caar + 1.96*se.cumsum()).values,
                        alpha=0.12, color=color)
    ax.axhline(0, color="black", lw=0.8, linestyle="--")
    ax.axvline(0, color="gray",  lw=0.8, linestyle=":")
    ax.set_title(ASSETS[key]["label"])
    ax.set_xlabel("이벤트 상대일")
    ax.set_ylabel("CAAR (%)")
    ax.legend(fontsize=9)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(1))
    ax.grid(True, alpha=0.3)
plt.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "03_caar_pos_neg_equity.png"), dpi=150)
plt.close()
print("  저장: 03_caar_pos_neg_equity.png")

# ── 8-4. 전체 vs 오염 제외 비교 (t=0, [-1,+1])
fig, axes = plt.subplots(1, 4, figsize=(16, 4), sharey=False)
fig.suptitle("전체 vs 오염 제외 ([-1,+1], t=0 AAR 비교)", fontsize=12, fontweight="bold")
for ax, key in zip(axes, ASSETS.keys()):
    cfg  = ASSETS[key]
    unit = cfg["unit"]
    if (key, 1) not in RESULTS:
        ax.set_title(cfg["label"]); continue
    res    = RESULTS[(key, 1)]
    n_full = len(res["ar"])
    n_cl   = len(res["ar_clean"])
    if n_cl < 5:
        ax.set_title(cfg["label"]); ax.text(0.5, 0.5, f"clean < 5건", ha="center", va="center", transform=ax.transAxes); continue
    st_cl  = compute_stats(res["ar_clean"], res["meta_clean"])
    vals  = [res["ar"][0].mean(),       res["ar_clean"][0].mean()]
    errs  = [res["ar"][0].std(ddof=1)/np.sqrt(n_full),
             res["ar_clean"][0].std(ddof=1)/np.sqrt(n_cl)]
    clrs  = ["#5dade2", "#f39c12"]
    xlbls = [f"전체\n({n_full}건)", f"오염 제외\n({n_cl}건)"]
    bars  = ax.bar(xlbls, vals, color=clrs, alpha=0.8, edgecolor="white", width=0.5)
    ax.errorbar([0, 1], vals, yerr=errs, fmt="none", color="black", capsize=5)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title(f"{cfg['label']} ({unit})", fontsize=10)
    ax.set_ylabel(f"AAR t=0 ({unit})")
    for i, (st_use, p_use) in enumerate([(res["stats"], res["stats"].loc[0,"p_bmp"]),
                                          (st_cl, st_cl.loc[0,"p_bmp"])]):
        sig_mark = "★" if p_use < 0.05 else ""
        ax.text(i, vals[i] + errs[i]*1.2 + 0.01,
                f"p={p_use:.3f}{sig_mark}", ha="center", fontsize=8, color="red" if sig_mark else "gray")
    ax.grid(True, alpha=0.3, axis="y")
plt.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "04_full_vs_clean.png"), dpi=150)
plt.close()
print("  저장: 04_full_vs_clean.png")

# ── 8-5. Placebo 분포 (KOSPI 기준)
if "KOSPI" in PLACEBO:
    pb  = PLACEBO["KOSPI"]
    sim = pb["sim_caars"]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.hist(sim, bins=50, color="#95a5a6", edgecolor="white", alpha=0.8, label="Placebo (2,000회)")
    ax.axvline(pb["actual_caar"], color="#e74c3c", lw=2,
               label=f"실제 CAAR = {pb['actual_caar']:+.4f}%")
    ax.axvline(np.percentile(sim, 2.5),  color="navy", lw=1.2, linestyle="--", label="95% CI")
    ax.axvline(np.percentile(sim, 97.5), color="navy", lw=1.2, linestyle="--")
    ax.set_xlabel("전체 CAAR (%)")
    ax.set_ylabel("빈도")
    ax.set_title(f"Placebo 검정 — KOSPI ([-5,+5])  p = {pb['p_placebo']:.4f}", fontsize=11)
    ax.legend(fontsize=9)
    plt.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "05_placebo_kospi.png"), dpi=150)
    plt.close()
    print("  저장: 05_placebo_kospi.png")

# ──────────────────────────────────────────────────────────────
# 9. 결과 테이블 출력 및 CSV 저장
# ──────────────────────────────────────────────────────────────
print("\n" + "=" * 58)

all_rows = []
for key, cfg in ASSETS.items():
    for WINDOW in WINDOWS:
        if (key, WINDOW) not in RESULTS:
            continue
        res = RESULTS[(key, WINDOW)]
        st  = res["stats"]
        n   = len(res["ar"])
        for day in DAYS[WINDOW]:
            if day not in st.index:
                continue
            all_rows.append({
                "변수"   : cfg["label"],
                "윈도우" : res["wlbl"],
                "상대일" : f"{day:+d}",
                "N"      : str(n),
                f"AAR"   : f"{st.loc[day,'AAR']:+.4f}",
                "CAAR"   : f"{st.loc[day,'CAAR']:+.4f}",
                "단위"   : cfg["unit"],
                "t_BMP"  : f"{st.loc[day,'t_bmp']:+.3f}",
                "p_BMP"  : f"{st.loc[day,'p_bmp']:.4f}",
                "부호p"  : f"{st.loc[day,'sign_p']:.4f}",
                "유의"   : "★" if st.loc[day,"sig"] else "",
            })

all_df = pd.DataFrame(all_rows)
all_df.to_csv(os.path.join(OUT_DIR, "results_all.csv"), index=False, encoding="utf-8-sig")

# 유의한 결과만 출력
sig_df = all_df[all_df["유의"] == "★"].reset_index(drop=True)
if len(sig_df):
    print_table(sig_df.drop(columns=["유의"]), "유의한 결과 (BMP p < 0.05)")
else:
    print("\n  * 통계적으로 유의한 결과 없음 (BMP p < 0.05)")

# t=0 요약
t0_rows = []
for key, cfg in ASSETS.items():
    for WINDOW in WINDOWS:
        if (key, WINDOW) not in RESULTS:
            continue
        res = RESULTS[(key, WINDOW)]
        st  = res["stats"]
        n   = len(res["ar"])
        n_cl = len(res["ar_clean"])
        if n_cl >= 5:
            st_cl = compute_stats(res["ar_clean"], res["meta_clean"])
            p_cl  = f"{st_cl.loc[0,'p_bmp']:.4f}"
        else:
            p_cl = "—"
        t0_rows.append({
            "변수"        : cfg["label"],
            "윈도우"      : res["wlbl"],
            "단위"        : cfg["unit"],
            "N(전체)"     : str(n),
            "AAR(t=0)"   : f"{res['ar'][0].mean():+.4f}",
            "t_BMP"       : f"{st.loc[0,'t_bmp']:+.3f}",
            "p(전체)"     : f"{st.loc[0,'p_bmp']:.4f}",
            "p(clean)"    : p_cl,
            "유의"        : "★" if st.loc[0,"sig"] else "",
        })
print_table(pd.DataFrame(t0_rows), "이벤트 당일(t=0) 전체 요약")

# Placebo
if PLACEBO:
    pb_rows = []
    for key in ASSETS:
        if key not in PLACEBO:
            continue
        pb = PLACEBO[key]
        pb_rows.append({
            "변수"      : ASSETS[key]["label"],
            "실제 CAAR" : f"{pb['actual_caar']:+.4f}{ASSETS[key]['unit']}",
            "Placebo μ" : f"{pb['sim_mean']:+.4f}{ASSETS[key]['unit']}",
            "p_placebo" : f"{pb['p_placebo']:.4f}",
            "유의"      : "★" if pb["p_placebo"] < 0.05 else "",
        })
    print_table(pd.DataFrame(pb_rows), "Placebo 검정 요약 ([-5,+5])")

pd.DataFrame(t0_rows).to_csv(
    os.path.join(OUT_DIR, "results_t0_summary.csv"), index=False, encoding="utf-8-sig"
)

print(f"\n{'─'*58}")
print(f"완료. 결과 → {OUT_DIR}")
print(f"{'─'*58}")
