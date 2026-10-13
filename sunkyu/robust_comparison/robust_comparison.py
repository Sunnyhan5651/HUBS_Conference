"""
robust_comparison.py
────────────────────────────────────────────────────────────────
Main(22건) vs Robust(49건) 표본 비교 분석
: 4개 백테스트 전략 전체 변수를 재검증

포함 변수 (11개):
  [미국 t0]  VIX, S&P 500, NASDAQ, 미국채 2Y, 미국채 10Y
  [한국 t0]  USD/KRW, KOSPI, KOSDAQ, 국고채 3Y, 국고채 10Y, BOK 기준금리(참고)

핵심 질문: Robust 49건으로 표본 확대 시 어떤 변수가 유의해지는가?
────────────────────────────────────────────────────────────────
"""

import os, sys, re, json, unicodedata, warnings
import urllib.request
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.font_manager as fm
import matplotlib.gridspec as gridspec
from fredapi import Fred
from scipy import stats

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from config import FRED_API_KEY, ECOS_API_KEY

try:
    import FinanceDataReader as fdr
except ImportError:
    raise ImportError("pip install finance-datareader")

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

def _dw(s):
    return sum(2 if unicodedata.east_asian_width(c) in ("W","F") else 1 for c in str(s))

def _pad(s, w, align="right"):
    s = str(s); p = w - _dw(s)
    return s + " "*p if align == "left" else " "*p + s

def print_table(df, title=""):
    cols = list(df.columns)
    rows = [[str(df.iloc[i,j]) for j in range(len(cols))] for i in range(len(df))]
    cw   = [max(_dw(c), max((_dw(r[j]) for r in rows), default=0)) for j,c in enumerate(cols)]
    sep  = "─" * (sum(cw) + 3*len(cols) + 1)
    if title:
        print(f"\n{sep}\n  {title}")
    print(sep)
    print("│ " + " │ ".join(_pad(c, cw[j], "left") for j,c in enumerate(cols)) + " │")
    print(sep)
    for row in rows:
        print("│ " + " │ ".join(_pad(v, cw[j]) for j,v in enumerate(row)) + " │")
    print(sep)

# ──────────────────────────────────────────────────────────────
# 경로
# ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
OUT_DIR  = os.path.join(BASE_DIR, "output")
os.makedirs(OUT_DIR, exist_ok=True)

EVENT_XLS = os.path.join(DATA_DIR, "이벤트 리스트 제안.xlsx")
START     = "2015-01-01"
EST_LEN   = 120

# ──────────────────────────────────────────────────────────────
# 변수 정의 (11개)
# ──────────────────────────────────────────────────────────────
# t0_col  : 이벤트 기준 컬럼
# source  : fred / fdr / ecos
# unit    : % (pct_change×100) / bp (diff×100)
# dir_mult: +1 상승 가설 / -1 하락 가설 / 0 무방향
ASSETS = {
    # ── 미국 t0 변수
    "VIX"    : dict(t0="미국 주식 t0", source="fred", code="VIXCLS",    unit="%",  dir_mult=-1, label="VIX",      grp="미국 t0", color="#e74c3c"),
    "SP500"  : dict(t0="미국 주식 t0", source="fred", code="SP500",     unit="%",  dir_mult=+1, label="S&P 500",  grp="미국 t0", color="#2471a3"),
    "NASDAQ" : dict(t0="미국 주식 t0", source="fred", code="NASDAQCOM", unit="%",  dir_mult=+1, label="NASDAQ",   grp="미국 t0", color="#1a9e6a"),
    "UST_2Y" : dict(t0="미국 주식 t0", source="fred", code="DGS2",      unit="bp", dir_mult=0,  label="미국채 2Y",grp="미국 t0", color="#8e44ad"),
    "UST_10Y": dict(t0="미국 주식 t0", source="fred", code="DGS10",     unit="bp", dir_mult=0,  label="미국채 10Y",grp="미국 t0",color="#d68910"),
    # ── 한국 t0 변수
    "USDKRW" : dict(t0="한국 주식 t0", source="fred", code="DEXKOUS",   unit="%",  dir_mult=-1, label="USD/KRW",  grp="한국 t0", color="#e67e22"),
    "KOSPI"  : dict(t0="한국 주식 t0", source="fdr",  code="KS11",      unit="%",  dir_mult=+1, label="KOSPI",    grp="한국 t0", color="#2ecc71"),
    "KOSDAQ" : dict(t0="한국 주식 t0", source="fdr",  code="KQ11",      unit="%",  dir_mult=+1, label="KOSDAQ",   grp="한국 t0", color="#27ae60"),
    "KTB_3Y" : dict(t0="한국 주식 t0", source="ecos", code="010200000", unit="bp", dir_mult=0,  label="국고채 3Y",grp="한국 t0", color="#16a085"),
    "KTB_10Y": dict(t0="한국 주식 t0", source="ecos", code="010210000", unit="bp", dir_mult=0,  label="국고채 10Y",grp="한국 t0",color="#0e6655"),
}

# ──────────────────────────────────────────────────────────────
# 데이터 로드
# ──────────────────────────────────────────────────────────────
print("=" * 62)
print("데이터 로딩 중...")
print("=" * 62)

_fred = Fred(api_key=FRED_API_KEY)

def get_fred(code):
    s = _fred.get_series(code, observation_start=START)
    s.index.name = "date"
    return s.ffill().dropna()

def get_fdr(code):
    df = fdr.DataReader(code, START)
    s  = df["Close"].copy()
    s.index = pd.to_datetime(s.index)
    s.index.name = "date"
    return s.sort_index()

def get_ecos(item_code, cycle="D"):
    stat = "817Y002"
    start, end = "20150101", "20261231"
    url = (f"https://ecos.bok.or.kr/api/StatisticSearch/"
           f"{ECOS_API_KEY}/json/kr/1/10000/"
           f"{stat}/{cycle}/{start}/{end}/{item_code}")
    with urllib.request.urlopen(url, timeout=30) as r:
        data = json.loads(r.read())
    rows = data["StatisticSearch"]["row"]
    s = pd.Series(
        {pd.to_datetime(r["TIME"]): float(r["DATA_VALUE"]) for r in rows},
        name=item_code
    )
    s.index.name = "date"
    return s.sort_index()

price_data = {}
for key, cfg in ASSETS.items():
    src = cfg["source"]
    if src == "fred":
        s = get_fred(cfg["code"])
    elif src == "fdr":
        s = get_fdr(cfg["code"])
    else:
        s = get_ecos(cfg["code"])
    price_data[key] = s
    print(f"  {cfg['label']:12s}: {len(s)}행  {s.index[0].date()}~{s.index[-1].date()}")

# ──────────────────────────────────────────────────────────────
# 이벤트 로드 (Main 22 / Robust 49)
# ──────────────────────────────────────────────────────────────
print("\n이벤트 로딩...")
ev_xl = pd.read_excel(EVENT_XLS, sheet_name="이벤트 리스트")
for col in ["미국 주식 t0", "한국 주식 t0"]:
    ev_xl[col] = pd.to_datetime(ev_xl[col])
ev_xl["방향"] = pd.to_numeric(ev_xl["방향(+1/0/−1)"], errors="coerce")

SAMPLES = {
    "Main"   : ev_xl[ev_xl["표본"] == "Main"].copy().reset_index(drop=True),
    "Robust" : ev_xl[ev_xl["표본"].isin(["Main","Robust"])].copy().reset_index(drop=True),
}
print(f"  Main 표본: {len(SAMPLES['Main'])}건  /  Robust 표본: {len(SAMPLES['Robust'])}건")

# ──────────────────────────────────────────────────────────────
# 오염 판정
# ──────────────────────────────────────────────────────────────
def is_contaminated(macro_text, window=2):
    text = str(macro_text)
    offsets = []
    for m in re.finditer(r"(FOMC|CPI)[^(]*\(T([+\-−]?\d+)\)", text):
        try:
            offsets.append(int(m.group(2).replace("−","-")))
        except ValueError:
            pass
    if re.search(r"(FOMC|CPI)[^\n]*당일", text): offsets.append(0)
    if re.search(r"(FOMC|CPI)[^\n]*\[", text): offsets.append(0)
    return any(abs(o) <= window for o in offsets)

# ──────────────────────────────────────────────────────────────
# 이벤트 스터디 엔진
# ──────────────────────────────────────────────────────────────
def run_event_study(price_series, event_df, t0_col, unit, window=5):
    """AR matrix + meta 반환"""
    if unit == "%":
        dy = price_series.ffill().pct_change().dropna() * 100
    else:  # bp
        dy = price_series.ffill().diff().dropna() * 100

    trading_days = dy.index
    ar_rows, meta_list = [], []

    for _, row in event_df.iterrows():
        event_date = pd.Timestamp(row[t0_col])
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
        ar_rows.append(ar)
        meta_list.append({
            "direction"   : row.get("방향", np.nan),
            "sigma_est"   : est_dy.std(ddof=1),
            "contaminated": is_contaminated(row.get("매크로 일정 겹침","—")),
        })

    cols      = list(range(-window, window+1))
    ar_matrix = pd.DataFrame(ar_rows, columns=cols) if ar_rows else pd.DataFrame(columns=cols)
    return ar_matrix, meta_list


def t0_stats(ar_matrix, meta):
    """t=0 BMP 통계 반환 (dict)"""
    if ar_matrix.empty or 0 not in ar_matrix.columns:
        return dict(n=0, aar=np.nan, t_bmp=np.nan, p_bmp=np.nan, sign_p=np.nan)

    ar_day = ar_matrix[0].values
    n      = len(ar_day)
    sigmas = np.array([m["sigma_est"] for m in meta])
    sigmas = np.where(sigmas < 1e-8, np.nan, sigmas)
    sar    = ar_day / sigmas
    sar_v  = sar[~np.isnan(sar)]

    if len(sar_v) < 2:
        return dict(n=n, aar=np.mean(ar_day), t_bmp=np.nan, p_bmp=np.nan, sign_p=np.nan)

    t_bmp  = np.mean(sar_v) / (np.std(sar_v, ddof=1) / np.sqrt(len(sar_v)))
    p_bmp  = 2 * (1 - stats.t.cdf(abs(t_bmp), df=len(sar_v)-1))
    pos    = int(np.sum(ar_day > 0))
    sign_p = 2 * min(stats.binom.cdf(pos, n, 0.5),
                     1 - stats.binom.cdf(pos-1, n, 0.5))
    return dict(n=n, aar=np.mean(ar_day), t_bmp=t_bmp, p_bmp=p_bmp, sign_p=sign_p)


def placebo(ar_matrix, meta, price_series, unit, window=5, n_sim=2000):
    if unit == "%":
        dy = price_series.ffill().pct_change().dropna() * 100
    else:
        dy = price_series.ffill().diff().dropna() * 100

    trading_days = dy.index
    actual_caar  = ar_matrix.values.sum(axis=1).mean() if not ar_matrix.empty else np.nan
    sim_caars    = []

    for _ in range(n_sim):
        valid = trading_days[EST_LEN + window + 1: -window - 1]
        if len(valid) == 0:
            break
        sim_cars = []
        for _ in range(len(meta)):
            idx    = np.random.randint(len(valid))
            t0_pos = trading_days.get_loc(valid[idx])
            es     = t0_pos - window - 1
            ss     = es - EST_LEN
            if ss < 0:
                continue
            mu  = dy.iloc[ss:es].mean()
            ev  = dy.iloc[t0_pos - window: t0_pos + window + 1]
            if len(ev) < 2*window+1:
                continue
            sim_cars.append((ev.values - mu).sum())
        if sim_cars:
            sim_caars.append(np.mean(sim_cars))

    sim_caars = np.array(sim_caars)
    p_up   = np.mean(sim_caars >= actual_caar)
    p_down = np.mean(sim_caars <= actual_caar)
    return dict(actual_caar=actual_caar, p_placebo=2*min(p_up,p_down), sim_caars=sim_caars)

# ──────────────────────────────────────────────────────────────
# 전체 실행
# ──────────────────────────────────────────────────────────────
print("\n" + "=" * 62)
print("이벤트 스터디 실행 중 (Main vs Robust 비교)...")
print("=" * 62)

WINDOW  = 5
RESULTS = {}  # (key, sample_name) → dict

for key, cfg in ASSETS.items():
    ps   = price_data[key]
    t0c  = cfg["t0"]
    unit = cfg["unit"]
    print(f"\n── {cfg['label']} ({'%' if unit=='%' else 'bp'}) ──")

    for sname, ev_df in SAMPLES.items():
        ar_mat, meta = run_event_study(ps, ev_df, t0c, unit, WINDOW)
        if ar_mat.empty:
            print(f"  {sname:7s}: 유효 이벤트 없음")
            continue

        st    = t0_stats(ar_mat, meta)
        n_cl  = sum(1 for m in meta if not m["contaminated"])
        cl_idx = [i for i,m in enumerate(meta) if not m["contaminated"]]
        ar_cl  = ar_mat.iloc[cl_idx].reset_index(drop=True)
        mt_cl  = [meta[i] for i in cl_idx]
        st_cl  = t0_stats(ar_cl, mt_cl) if len(ar_cl) >= 5 else dict(p_bmp=np.nan)

        pb = placebo(ar_mat, meta, ps, unit, WINDOW) if sname == "Robust" else None

        RESULTS[(key, sname)] = {
            "ar": ar_mat, "meta": meta, "stats": st,
            "n_clean": n_cl, "p_clean": st_cl["p_bmp"],
            "pb": pb,
        }
        print(f"  {sname:7s}: N={st['n']:2d}  AAR={st['aar']:+.4f}  "
              f"t={st['t_bmp']:+.3f}  p={st['p_bmp']:.4f}  "
              f"p(clean)={st_cl['p_bmp']:.4f}" if st_cl["p_bmp"] is not np.nan
              else f"  {sname:7s}: N={st['n']:2d}  AAR={st['aar']:+.4f}  t={st['t_bmp']:+.3f}  p={st['p_bmp']:.4f}")

# ──────────────────────────────────────────────────────────────
# 결과 비교 테이블
# ──────────────────────────────────────────────────────────────
print("\n" + "=" * 62)

rows = []
for key, cfg in ASSETS.items():
    r_m = RESULTS.get((key, "Main"))
    r_r = RESULTS.get((key, "Robust"))
    if r_m is None or r_r is None:
        continue

    p_m = r_m["stats"]["p_bmp"]
    p_r = r_r["stats"]["p_bmp"]
    delta = p_m - p_r  # 양수 = Robust에서 p-value 낮아짐(개선)

    def sig_mark(p):
        if pd.isna(p): return "—"
        if p < 0.01:   return f"{p:.4f} ★★"
        if p < 0.05:   return f"{p:.4f} ★"
        if p < 0.10:   return f"{p:.4f} †"
        return f"{p:.4f}"

    rows.append({
        "그룹"       : cfg["grp"],
        "변수"       : cfg["label"],
        "단위"       : cfg["unit"],
        "N(Main)"    : str(r_m["stats"]["n"]),
        "p(Main)"    : sig_mark(p_m),
        "N(Robust)"  : str(r_r["stats"]["n"]),
        "p(Robust)"  : sig_mark(p_r),
        "p(clean,R)" : sig_mark(r_r["p_clean"]),
        "변화"       : ("↓개선" if delta > 0.05 else "↑악화" if delta < -0.05 else "유사"),
    })

cmp_df = pd.DataFrame(rows)
print_table(cmp_df, "Main(22건) vs Robust(49건) — t=0 BMP p-value 비교 (★p<0.05  ★★p<0.01  †p<0.10)")
cmp_df.to_csv(os.path.join(OUT_DIR, "comparison_main_vs_robust.csv"), index=False, encoding="utf-8-sig")

# Robust Placebo 요약
pb_rows = []
for key, cfg in ASSETS.items():
    r_r = RESULTS.get((key, "Robust"))
    if r_r is None or r_r["pb"] is None:
        continue
    pb = r_r["pb"]
    pb_rows.append({
        "변수"       : cfg["label"],
        "실제 CAAR"  : f"{pb['actual_caar']:+.4f}{'%' if cfg['unit']=='%' else 'bp'}",
        "p(placebo)" : f"{pb['p_placebo']:.4f}" + (" ★" if pb['p_placebo'] < 0.05 else ""),
    })
print_table(pd.DataFrame(pb_rows), "Robust(49건) Placebo 검정 요약 ([-5,+5])")

# ──────────────────────────────────────────────────────────────
# 시각화
# ──────────────────────────────────────────────────────────────
print("\n차트 생성 중...")

KEYS   = list(ASSETS.keys())
LABELS = [ASSETS[k]["label"] for k in KEYS]
COLORS = [ASSETS[k]["color"] for k in KEYS]

# ── 차트 1: p-value 비교 도트 플롯
fig, ax = plt.subplots(figsize=(13, 6))
y_pos = np.arange(len(KEYS))

p_main   = [RESULTS.get((k,"Main"),  {}).get("stats",{}).get("p_bmp", np.nan) for k in KEYS]
p_robust = [RESULTS.get((k,"Robust"),{}).get("stats",{}).get("p_bmp", np.nan) for k in KEYS]
p_clean  = [RESULTS.get((k,"Robust"),{}).get("p_clean", np.nan) for k in KEYS]

for i, (k, pm, pr, pc) in enumerate(zip(KEYS, p_main, p_robust, p_clean)):
    if not np.isnan(pm) and not np.isnan(pr):
        ax.plot([pm, pr], [i, i], color="lightgray", lw=1.5, zorder=1)
    ax.scatter(pm, i, color=COLORS[i], s=100, zorder=3, label="Main" if i==0 else "")
    ax.scatter(pr, i, color=COLORS[i], s=60, marker="D", zorder=3, label="Robust" if i==0 else "")
    if not np.isnan(pc):
        ax.scatter(pc, i, color=COLORS[i], s=50, marker="x", lw=1.5, zorder=3, label="Robust clean" if i==0 else "")

ax.axvline(0.05, color="red",   lw=1.2, linestyle="--", alpha=0.8, label="p=0.05")
ax.axvline(0.10, color="orange",lw=1.0, linestyle=":",  alpha=0.6, label="p=0.10")
ax.set_yticks(y_pos); ax.set_yticklabels(LABELS, fontsize=10)
ax.set_xlabel("BMP p-value (t=0)", fontsize=11)
ax.set_title("Main(●) vs Robust(◆) vs Robust clean(✕) — t=0 유의수준 비교",
             fontsize=12, fontweight="bold")
ax.set_xlim(-0.02, 1.02)
ax.legend(loc="lower right", fontsize=9)
ax.grid(True, alpha=0.3, axis="x")
ax.invert_yaxis()
plt.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "01_pvalue_dotplot.png"), dpi=150)
plt.close()
print("  저장: 01_pvalue_dotplot.png")

# ── 차트 2: CAAR 비교 (Main vs Robust, 4×3 그리드)
n_vars = len(KEYS)
ncols  = 4
nrows  = (n_vars + ncols - 1) // ncols
fig, axes = plt.subplots(nrows, ncols, figsize=(16, nrows*3.5))
axes_flat = axes.flatten()
days = list(range(-WINDOW, WINDOW+1))

for idx, key in enumerate(KEYS):
    ax  = axes_flat[idx]
    cfg = ASSETS[key]
    for sname, ls, lw in [("Main","--",1.5), ("Robust","-",2)]:
        r = RESULTS.get((key, sname))
        if r is None or r["ar"].empty:
            continue
        ar  = r["ar"]
        aar = ar.mean(axis=0)
        se  = ar.std(axis=0, ddof=1) / np.sqrt(len(ar))
        caar = aar.cumsum()
        ax.plot(days, caar.values, ls, lw=lw, color=cfg["color"],
                label=f"{sname}(N={len(ar)})")
        ax.fill_between(days,
                        (caar - 1.96*se.cumsum()).values,
                        (caar + 1.96*se.cumsum()).values,
                        alpha=0.08, color=cfg["color"])
    ax.axhline(0, color="black", lw=0.7, linestyle="--")
    ax.axvline(0, color="gray",  lw=0.7, linestyle=":")
    unit_lbl = "%" if cfg["unit"]=="%" else "bp"
    ax.set_title(f"{cfg['label']} ({unit_lbl})", fontsize=10)
    ax.set_xlabel("상대일", fontsize=8)
    ax.legend(fontsize=7)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(2))
    ax.grid(True, alpha=0.25)

for idx in range(n_vars, len(axes_flat)):
    axes_flat[idx].set_visible(False)

fig.suptitle("Main(점선) vs Robust(실선) CAAR 비교 — 전 변수", fontsize=13, fontweight="bold")
plt.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "02_caar_all_comparison.png"), dpi=150)
plt.close()
print("  저장: 02_caar_all_comparison.png")

# ── 차트 3: t=0 AAR 막대 비교 (Main vs Robust)
fig, axes = plt.subplots(2, 5, figsize=(18, 7))
axes_flat = axes.flatten()

for idx, key in enumerate(KEYS):
    ax  = axes_flat[idx]
    cfg = ASSETS[key]
    aars = []; errs = []; xlbls = []; colors_bar = []
    for sname, c in [("Main","#95a5a6"), ("Robust", cfg["color"])]:
        r = RESULTS.get((key, sname))
        if r is None or r["ar"].empty:
            continue
        ar  = r["ar"]
        aar = ar[0].mean()
        se  = ar[0].std(ddof=1) / np.sqrt(len(ar))
        p   = r["stats"]["p_bmp"]
        mark = " ★" if p < 0.05 else (" †" if p < 0.10 else "")
        aars.append(aar); errs.append(1.96*se)
        xlbls.append(f"{sname}({len(ar)}){mark}")
        colors_bar.append(c)
    if not aars:
        continue
    bars = ax.bar(range(len(aars)), aars, color=colors_bar, edgecolor="white",
                  width=0.5, alpha=0.85)
    ax.errorbar(range(len(aars)), aars, yerr=errs,
                fmt="none", color="black", capsize=5, lw=1.2)
    ax.axhline(0, color="black", lw=0.7)
    ax.set_xticks(range(len(xlbls))); ax.set_xticklabels(xlbls, fontsize=8)
    ax.set_title(f"{cfg['label']}", fontsize=9)
    unit_lbl = "%" if cfg["unit"]=="%" else "bp"
    ax.set_ylabel(f"AAR t=0 ({unit_lbl})", fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")

for idx in range(n_vars, len(axes_flat)):
    axes_flat[idx].set_visible(False)

fig.suptitle("t=0 AAR 비교 (Main vs Robust)  ★p<0.05  †p<0.10", fontsize=13, fontweight="bold")
plt.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "03_aar_t0_comparison.png"), dpi=150)
plt.close()
print("  저장: 03_aar_t0_comparison.png")

# ── 차트 4: Placebo 분포 (Robust, 전 변수)
ncols = 4; nrows = (n_vars + ncols - 1) // ncols
fig, axes = plt.subplots(nrows, ncols, figsize=(16, nrows*3.5))
axes_flat = axes.flatten()

for idx, key in enumerate(KEYS):
    ax  = axes_flat[idx]
    cfg = ASSETS[key]
    r   = RESULTS.get((key,"Robust"))
    if r is None or r["pb"] is None:
        ax.set_title(cfg["label"]); continue
    pb  = r["pb"]
    sim = pb["sim_caars"]
    ax.hist(sim, bins=50, color="#bdc3c7", edgecolor="white", alpha=0.8)
    ax.axvline(pb["actual_caar"], color=cfg["color"], lw=2,
               label=f"실제={pb['actual_caar']:+.3f}")
    ax.axvline(np.percentile(sim, 2.5),  color="navy", lw=1, linestyle="--")
    ax.axvline(np.percentile(sim, 97.5), color="navy", lw=1, linestyle="--",
               label="95% CI")
    p  = pb["p_placebo"]
    ax.set_title(f"{cfg['label']}  p={p:.4f}" + (" ★" if p<0.05 else ""), fontsize=9)
    ax.set_xlabel("CAAR", fontsize=8); ax.legend(fontsize=7)

for idx in range(n_vars, len(axes_flat)):
    axes_flat[idx].set_visible(False)

fig.suptitle("Placebo 검정 — Robust(49건) 전 변수", fontsize=13, fontweight="bold")
plt.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "04_placebo_robust.png"), dpi=150)
plt.close()
print("  저장: 04_placebo_robust.png")

# ──────────────────────────────────────────────────────────────
# 최종 해석 요약 출력
# ──────────────────────────────────────────────────────────────
print("\n" + "=" * 62)
print("  결과 요약")
print("=" * 62)

sig_any = [(k, ASSETS[k]["label"], RESULTS[(k,"Robust")]["stats"]["p_bmp"])
           for k in KEYS if (k,"Robust") in RESULTS
           and RESULTS[(k,"Robust")]["stats"]["p_bmp"] < 0.10]

if sig_any:
    print(f"\n  Robust에서 p < 0.10 진입 변수:")
    for k, lbl, p in sig_any:
        p_m = RESULTS.get((k,"Main"),{}).get("stats",{}).get("p_bmp", np.nan)
        print(f"    {lbl:12s}  p(Main)={p_m:.4f} → p(Robust)={p:.4f}")
else:
    print("\n  ⇒ Robust 표본에서도 t=0 유의 변수 없음 (모든 변수 p > 0.10)")

print(f"\n  완료. 결과 → {OUT_DIR}")
print("=" * 62)
