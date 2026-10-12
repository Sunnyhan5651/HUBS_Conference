"""
USD_KRW_backtest.py
────────────────────────────────────────────────────────────────
원/달러 환율 이벤트 드리븐 백테스트
: 디지털 자산 제도화 이벤트 → USD/KRW 충격 분석

데이터:
  USD/KRW  : FRED DEXKOUS (fredapi)
  BOK 기준금리: ECOS API 722Y001 (금리 변경일 탐지)

이벤트 t0 : 한국 주식 t0 (한국 시장 첫 반영일)
이벤트 창  : [-5, +5] (메인) / [-1, +1] (보조)
추정 창    : 이벤트 전 120 영업일
오염 기준  : FOMC·CPI가 ±2 영업일 내 → 전체 표본에 포함하되 별도 clean 표본 비교
────────────────────────────────────────────────────────────────
"""

import os, sys, json, re, unicodedata, warnings
import urllib.request
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.font_manager as fm
from fredapi import Fred
from scipy import stats

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from config import FRED_API_KEY, ECOS_API_KEY

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
# 0. 경로 설정
# ──────────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "..", "data")
OUT_DIR   = os.path.join(BASE_DIR, "output")
os.makedirs(OUT_DIR, exist_ok=True)

EVENT_XLS = os.path.join(DATA_DIR, "이벤트 리스트 제안.xlsx")

# ──────────────────────────────────────────────────────────────
# 1. FRED DEXKOUS (USD/KRW) 로드
# ──────────────────────────────────────────────────────────────
START = "2015-01-01"
_fred = Fred(api_key=FRED_API_KEY)

print("─" * 55)
print("USD/KRW 환율 로딩 중... (FRED DEXKOUS)")
krw = _fred.get_series("DEXKOUS", observation_start=START)
krw.name = "DEXKOUS"
krw.index.name = "date"
krw = krw.ffill().dropna()
print(f"  기간: {krw.index[0].date()} ~ {krw.index[-1].date()} | {len(krw)}행")
print(f"  최근값: {krw.iloc[-1]:.2f} KRW/USD")

# ──────────────────────────────────────────────────────────────
# 2. ECOS BOK 기준금리 로드 → 금리 변경일 탐지
# ──────────────────────────────────────────────────────────────
def get_ecos(stat_code, item_code, start="20150101", end="20261231", cycle="DD"):
    url = (f"https://ecos.bok.or.kr/api/StatisticSearch/"
           f"{ECOS_API_KEY}/json/kr/1/10000/"
           f"{stat_code}/{cycle}/{start}/{end}/{item_code}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        rows = data.get("StatisticSearch", {}).get("row", [])
        if not rows:
            return pd.Series(dtype=float, name=stat_code)
        s = pd.Series(
            {pd.Timestamp(row["TIME"]): float(row["DATA_VALUE"].replace(",", ""))
             for row in rows},
            name=stat_code,
        )
        s.index.name = "date"
        return s.sort_index()
    except Exception as e:
        print(f"  ECOS 로드 실패: {e}")
        return pd.Series(dtype=float, name=stat_code)

print("\nBOK 기준금리 로딩 중... (ECOS 722Y001)")
bok_rate = get_ecos("722Y001", "0001000")

if not bok_rate.empty:
    bok_changes = bok_rate[bok_rate.diff().abs() > 0.01].dropna()
    print(f"  데이터: {len(bok_rate)}행 | 금리 변경일: {len(bok_changes)}건")
    print("  최근 변경 이력 (5건):")
    prev_rate = bok_rate.shift(1)
    for d, v in list(bok_changes.items())[-5:]:
        prev = prev_rate.get(d, float("nan"))
        print(f"    {d.date()}  {prev:.2f}% → {v:.2f}%  ({v-prev:+.2f}%p)")
else:
    print("  BOK 데이터 로드 실패 → BOK 오염 판정 비활성화")
    bok_changes = pd.Series(dtype=float)

BOK_CHANGE_DATES = set(bok_changes.index.normalize()) if not bok_changes.empty else set()

# ──────────────────────────────────────────────────────────────
# 3. 이벤트 데이터 로드
# ──────────────────────────────────────────────────────────────
print("\n이벤트 데이터 로딩 중...")
ev_xl  = pd.read_excel(EVENT_XLS, sheet_name="이벤트 리스트")
ev_xl["한국 주식 t0"] = pd.to_datetime(ev_xl["한국 주식 t0"])
ev_xl["방향"]         = pd.to_numeric(ev_xl["방향(+1/0/−1)"], errors="coerce")
ev_main = ev_xl[ev_xl["표본"] == "Main"].copy().reset_index(drop=True)
print(f"  Main 표본: {len(ev_main)}건 | 이벤트 t0: 한국 주식 t0")

# ──────────────────────────────────────────────────────────────
# 4. 오염 판정
# ──────────────────────────────────────────────────────────────
STRICT = 2   # 오염 기준: ±2 영업일

def _fomc_cpi_offsets(macro_text):
    """매크로 일정 겹침 텍스트에서 FOMC/CPI T 오프셋 파싱"""
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

def is_bok_contaminated(event_date, trading_days, window=STRICT):
    if not BOK_CHANGE_DATES:
        return False
    future = trading_days[trading_days >= event_date]
    if len(future) == 0:
        return False
    t0_pos = trading_days.get_loc(future[0])
    start  = max(0, t0_pos - window)
    end    = min(len(trading_days) - 1, t0_pos + window)
    window_dates = set(trading_days[start:end + 1].normalize())
    return bool(window_dates & BOK_CHANGE_DATES)

# ──────────────────────────────────────────────────────────────
# 5. 이벤트 스터디 핵심 함수
# ──────────────────────────────────────────────────────────────
EST_LEN = 120

def run_event_study(price_series, event_df, date_col="한국 주식 t0", window=5):
    dy           = price_series.ffill().pct_change().dropna() * 100
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

        macro_text  = row.get("매크로 일정 겹침", "—")
        fomc_cpi    = is_fomc_cpi_contaminated(macro_text, STRICT)
        bok_cont    = is_bok_contaminated(event_date, trading_days, STRICT)

        ar_rows.append(ar)
        meta_list.append({
            "event_id"           : row.get("이벤트 ID", ""),
            "event_date"         : event_date,
            "t0"                 : t0_date,
            "direction"          : row.get("방향", np.nan),
            "category"           : row.get("카테고리", ""),
            "title"              : row.get("이벤트", ""),
            "sigma_est"          : est_dy.std(ddof=1),
            "contaminated_fc"    : fomc_cpi,
            "contaminated_bok"   : bok_cont,
            "contaminated"       : fomc_cpi or bok_cont,
        })

    cols      = list(range(-window, window + 1))
    ar_matrix = pd.DataFrame(ar_rows, columns=cols) if ar_rows else pd.DataFrame(columns=cols)
    return ar_matrix, meta_list

# ──────────────────────────────────────────────────────────────
# 6. 통계 검정 (BMP · 부호검정)
# ──────────────────────────────────────────────────────────────
def compute_stats(ar_matrix, meta, alpha=0.05):
    n = len(ar_matrix)
    rows = {}
    for day in ar_matrix.columns:
        ar_day = ar_matrix[day].values
        sigmas = np.array([m["sigma_est"] for m in meta])
        sigmas = np.where(sigmas < 1e-8, np.nan, sigmas)
        sar    = ar_day / sigmas
        sar_v  = sar[~np.isnan(sar)]

        if len(sar_v) < 2:
            rows[day] = dict(AAR=np.nan, CAAR=np.nan, t_bmp=np.nan,
                             p_bmp=np.nan, sign_p=np.nan, sig=False)
            continue

        t_bmp  = np.mean(sar_v) / (np.std(sar_v, ddof=1) / np.sqrt(len(sar_v)))
        p_bmp  = 2 * (1 - stats.t.cdf(abs(t_bmp), df=len(sar_v) - 1))
        pos    = int(np.sum(ar_day > 0))
        sign_p = 2 * min(stats.binom.cdf(pos, n, 0.5),
                         1 - stats.binom.cdf(pos - 1, n, 0.5))
        rows[day] = dict(AAR=np.mean(ar_day), t_bmp=t_bmp, p_bmp=p_bmp,
                         sign_p=sign_p, sig=p_bmp < alpha)

    df        = pd.DataFrame(rows).T
    df["CAAR"] = df["AAR"].cumsum()
    return df

# ──────────────────────────────────────────────────────────────
# 7. Placebo 검정
# ──────────────────────────────────────────────────────────────
def placebo_test(ar_matrix, meta, price_dy, window=5, n_sim=2000):
    trading_days = price_dy.index
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
            mu   = price_dy.iloc[est_start:est_end].mean()
            ev   = price_dy.iloc[t0_pos - window: t0_pos + window + 1]
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
# 8. 실행 — 두 이벤트 창
# ──────────────────────────────────────────────────────────────
krw_dy   = krw.ffill().pct_change().dropna() * 100
RES      = {}        # {window: {ar, meta, stats}}
DIR_RES  = {}        # {window: {ar_adj, stats, n}}

print("\n" + "═" * 55)
print("이벤트 스터디 실행 중...")

for WINDOW in [5, 1]:
    lbl = f"[-{WINDOW},+{WINDOW}]"
    ar_mat, meta = run_event_study(krw, ev_main, window=WINDOW)
    if ar_mat.empty:
        print(f"\n  {lbl}: 유효 이벤트 없음")
        continue

    st = compute_stats(ar_mat, meta)
    n_contam = sum(m["contaminated"] for m in meta)
    n_bok    = sum(m["contaminated_bok"] for m in meta)
    print(f"\n  {lbl}  유효 {len(ar_mat)}건 "
          f"(FOMC/CPI 오염 {sum(m['contaminated_fc'] for m in meta)}건, "
          f"BOK 오염 {n_bok}건)")
    print(f"    전체 CAAR: {ar_mat.values.sum(axis=1).mean():+.4f}%  "
          f"BMP t(t=0): {st.loc[0,'t_bmp']:+.2f}  p: {st.loc[0,'p_bmp']:.4f}")

    RES[WINDOW] = {"ar": ar_mat, "meta": meta, "stats": st, "label": lbl}

    # 방향 조정 (긍정이벤트 → KRW 강세 → DEXKOUS↓ → AR<0 → (-dir)×AR > 0)
    dirs  = np.array([m["direction"] for m in meta])
    valid = ~(np.isnan(dirs) | (dirs == 0))
    ar_d  = ar_mat.loc[valid].copy()
    d_val = dirs[valid]
    ar_adj = ar_d.multiply(-d_val, axis=0)
    st_adj = compute_stats(ar_adj, [m for m, v in zip(meta, valid) if v])
    DIR_RES[WINDOW] = {"ar_adj": ar_adj, "stats": st_adj, "n": int(valid.sum())}
    print(f"    방향 조정  {int(valid.sum())}건  "
          f"Dir-Adj CAAR: {ar_adj.values.sum(axis=1).mean():+.4f}%  "
          f"BMP t(t=0): {st_adj.loc[0,'t_bmp']:+.2f}  p: {st_adj.loc[0,'p_bmp']:.4f}")

# ──────────────────────────────────────────────────────────────
# 9. 오염 제외 비교 ([-1,+1])
# ──────────────────────────────────────────────────────────────
COMP_WIN = 1
clean_res = {}
if COMP_WIN in RES:
    ar_full  = RES[COMP_WIN]["ar"]
    meta_all = RES[COMP_WIN]["meta"]
    clean_idx = [i for i, m in enumerate(meta_all) if not m["contaminated"]]

    ar_clean   = ar_full.iloc[clean_idx].reset_index(drop=True)
    meta_clean = [meta_all[i] for i in clean_idx]
    n_all      = len(ar_full)
    n_clean    = len(ar_clean)

    st_full  = RES[COMP_WIN]["stats"]
    st_clean = compute_stats(ar_clean, meta_clean) if n_clean >= 5 else None
    clean_res = {"ar": ar_clean, "meta": meta_clean, "stats": st_clean,
                 "n_all": n_all, "n_clean": n_clean}

    print(f"\n오염 제외 비교 ([-1,+1])")
    print(f"  전체      {n_all}건  CAAR(t=0): {ar_full[0].mean():+.4f}%  "
          f"t: {st_full.loc[0,'t_bmp']:+.2f}")
    if st_clean is not None:
        print(f"  오염 제외  {n_clean}건  CAAR(t=0): {ar_clean[0].mean():+.4f}%  "
              f"t: {st_clean.loc[0,'t_bmp']:+.2f}")

# ──────────────────────────────────────────────────────────────
# 10. Placebo 검정 ([-5,+5])
# ──────────────────────────────────────────────────────────────
placebo = None
if 5 in RES:
    print("\nPlacebo 검정 실행 중 (2,000회)...")
    placebo = placebo_test(RES[5]["ar"], RES[5]["meta"], krw_dy, window=5)
    print(f"  실제 CAAR: {placebo['actual_caar']:+.4f}%  |  "
          f"Placebo μ: {placebo['sim_mean']:+.4f}%  |  "
          f"p = {placebo['p_placebo']:.4f}")

# ──────────────────────────────────────────────────────────────
# 11. 시각화
# ──────────────────────────────────────────────────────────────
print("\n차트 생성 중...")

DAYS = {5: list(range(-5, 6)), 1: list(range(-1, 2))}

# ── 11-1. CAAR 비교 (두 윈도우 × 원본/방향조정)
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
fig.suptitle("USD/KRW CAAR — 디지털 자산 제도화 이벤트 (Main 22건)", fontsize=13, fontweight="bold")

for ax, WINDOW in zip(axes, [5, 1]):
    if WINDOW not in RES:
        continue
    days = DAYS[WINDOW]
    ar_mat = RES[WINDOW]["ar"]
    aar    = ar_mat.mean(axis=0)
    caar   = aar.cumsum()
    se     = ar_mat.std(axis=0, ddof=1) / np.sqrt(len(ar_mat))
    ax.plot(days, caar.values, "b-o", ms=4, lw=2, label=f"전체 ({len(ar_mat)}건)")
    ax.fill_between(days,
                    (caar - 1.96 * se.cumsum()).values,
                    (caar + 1.96 * se.cumsum()).values,
                    alpha=0.1, color="blue")
    if WINDOW in DIR_RES:
        ar_adj = DIR_RES[WINDOW]["ar_adj"]
        aar_d  = ar_adj.mean(axis=0)
        caar_d = aar_d.cumsum()
        se_d   = ar_adj.std(axis=0, ddof=1) / np.sqrt(len(ar_adj))
        ax.plot(days, caar_d.values, "r--s", ms=4, lw=2,
                label=f"방향 조정 ({DIR_RES[WINDOW]['n']}건)")
        ax.fill_between(days,
                        (caar_d - 1.96 * se_d.cumsum()).values,
                        (caar_d + 1.96 * se_d.cumsum()).values,
                        alpha=0.08, color="red")
    ax.axhline(0, color="black", lw=0.8, linestyle="--")
    ax.axvline(0, color="gray",  lw=0.8, linestyle=":")
    ax.set_xlabel("이벤트 상대일 (t=0: 한국 주식 t0)")
    ax.set_ylabel("CAAR (%)")
    ax.set_title(f"이벤트 창 {RES[WINDOW]['label']}")
    ax.legend(fontsize=9)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(1))
    ax.grid(True, alpha=0.3)

plt.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "01_caar_comparison.png"), dpi=150)
plt.close()
print("  저장: 01_caar_comparison.png")

# ── 11-2. 일별 AAR 막대 ([-5,+5])
if 5 in RES:
    st    = RES[5]["stats"]
    aar   = RES[5]["ar"].mean(axis=0)
    se    = RES[5]["ar"].std(axis=0, ddof=1) / np.sqrt(len(RES[5]["ar"]))
    cols  = ["#e74c3c" if st.loc[d, "sig"] else "#95a5a6" for d in DAYS[5]]
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.bar(DAYS[5], aar.values, color=cols, edgecolor="white", width=0.7)
    ax.errorbar(DAYS[5], aar.values, yerr=1.96 * se.values,
                fmt="none", color="black", capsize=4, lw=1)
    ax.axhline(0, color="black", lw=0.8)
    ax.axvline(0, color="red",   lw=0.8, linestyle=":")
    ax.set_xlabel("이벤트 상대일")
    ax.set_ylabel("AAR (%)")
    ax.set_title("일별 평균 비정상 수익률 (빨강=BMP p<0.05)", fontsize=11)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(1))
    plt.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "02_aar_by_day.png"), dpi=150)
    plt.close()
    print("  저장: 02_aar_by_day.png")

# ── 11-3. 긍정 vs 부정 이벤트 CAAR
if 5 in RES:
    ar_mat = RES[5]["ar"]
    meta   = RES[5]["meta"]
    dirs   = np.array([m["direction"] for m in meta])
    fig, ax = plt.subplots(figsize=(11, 5))
    for mask, color, lbl in [
        (dirs == 1,  "#2ecc71", f"긍정 이벤트 (n={int((dirs==1).sum())})"),
        (dirs == -1, "#e74c3c", f"부정 이벤트 (n={int((dirs==-1).sum())})"),
    ]:
        if mask.sum() < 2:
            continue
        sub  = ar_mat.loc[mask]
        caar = sub.mean(axis=0).cumsum()
        se   = sub.std(axis=0, ddof=1) / np.sqrt(len(sub))
        ax.plot(DAYS[5], caar.values, lw=2, color=color, label=lbl)
        ax.fill_between(DAYS[5],
                        (caar - 1.96 * se.cumsum()).values,
                        (caar + 1.96 * se.cumsum()).values,
                        alpha=0.12, color=color)
    ax.axhline(0, color="black", lw=0.8, linestyle="--")
    ax.axvline(0, color="gray",  lw=0.8, linestyle=":")
    ax.set_xlabel("이벤트 상대일")
    ax.set_ylabel("CAAR (%)")
    ax.set_title("USD/KRW CAAR — 긍정 vs 부정 이벤트", fontsize=11, fontweight="bold")
    ax.legend(fontsize=10)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(1))
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "03_caar_pos_neg.png"), dpi=150)
    plt.close()
    print("  저장: 03_caar_pos_neg.png")

# ── 11-4. 전체 vs 오염 제외 ([-1,+1])
if clean_res and clean_res.get("stats") is not None:
    ar_full_c  = RES[COMP_WIN]["ar"]
    st_full_c  = RES[COMP_WIN]["stats"]
    ar_clean_c = clean_res["ar"]
    st_clean_c = clean_res["stats"]
    n_all_c    = clean_res["n_all"]
    n_clean_c  = clean_res["n_clean"]

    fig, axes = plt.subplots(1, 2, figsize=(13, 4), sharey=True)
    fig.suptitle("USD/KRW 전체 vs 오염 제외 비교 ([-1,+1])", fontsize=12, fontweight="bold")
    for ax, (ar_s, st_s, lbl) in zip(axes, [
        (ar_full_c,  st_full_c,  f"전체 ({n_all_c}건)"),
        (ar_clean_c, st_clean_c, f"오염 제외 ({n_clean_c}건)"),
    ]):
        caar_v = ar_s.mean(axis=0).cumsum()
        se_v   = ar_s.std(axis=0, ddof=1) / np.sqrt(len(ar_s))
        ax.plot(DAYS[1], caar_v.values, "-o", color="#3498db", lw=2)
        ax.fill_between(DAYS[1],
                        (caar_v - 1.96 * se_v.cumsum()).values,
                        (caar_v + 1.96 * se_v.cumsum()).values,
                        alpha=0.15, color="#3498db")
        ax.axhline(0, color="black", lw=0.8, linestyle="--")
        ax.axvline(0, color="red",   lw=0.8, linestyle=":")
        ax.set_title(lbl)
        ax.set_xlabel("상대일")
        ax.set_ylabel("CAAR (%)")
        ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "04_full_vs_clean.png"), dpi=150)
    plt.close()
    print("  저장: 04_full_vs_clean.png")

# ── 11-5. Placebo 분포
if placebo is not None:
    sim = placebo["sim_caars"]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.hist(sim, bins=50, color="#95a5a6", edgecolor="white", alpha=0.8, label="Placebo (2,000회)")
    ax.axvline(placebo["actual_caar"], color="#e74c3c", lw=2,
               label=f"실제 CAAR = {placebo['actual_caar']:+.4f}%")
    ax.axvline(np.percentile(sim, 2.5),  color="navy", lw=1.2, linestyle="--", label="95% CI")
    ax.axvline(np.percentile(sim, 97.5), color="navy", lw=1.2, linestyle="--")
    ax.set_xlabel("전체 CAAR (%)")
    ax.set_ylabel("빈도")
    ax.set_title(f"Placebo 검정 ([-5,+5])  —  p = {placebo['p_placebo']:.4f}", fontsize=11)
    ax.legend(fontsize=9)
    plt.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "05_placebo.png"), dpi=150)
    plt.close()
    print("  저장: 05_placebo.png")

# ──────────────────────────────────────────────────────────────
# 12. 결과 테이블 출력 및 CSV 저장
# ──────────────────────────────────────────────────────────────
print("\n" + "═" * 55)

# 전 이벤트 창 BMP 결과
all_rows = []
for WINDOW in [5, 1]:
    if WINDOW not in RES:
        continue
    st  = RES[WINDOW]["stats"]
    lbl = RES[WINDOW]["label"]
    n   = len(RES[WINDOW]["ar"])
    for day in DAYS[WINDOW]:
        all_rows.append({
            "윈도우" : lbl,
            "상대일" : f"{day:+d}",
            "N"      : str(n),
            "AAR(%)" : f"{st.loc[day,'AAR']:+.4f}",
            "CAAR(%)": f"{st.loc[day,'CAAR']:+.4f}",
            "t_BMP"  : f"{st.loc[day,'t_bmp']:+.3f}",
            "p_BMP"  : f"{st.loc[day,'p_bmp']:.4f}",
            "부호p"  : f"{st.loc[day,'sign_p']:.4f}",
            "유의"   : "★" if st.loc[day,"sig"] else "",
        })
all_df = pd.DataFrame(all_rows)
all_df.to_csv(os.path.join(OUT_DIR, "results_all.csv"), index=False, encoding="utf-8-sig")

sig_df = all_df[all_df["유의"] == "★"].reset_index(drop=True)
if len(sig_df):
    print_table(sig_df, "유의한 결과 (BMP p < 0.05)")
else:
    print("\n  * 통계적으로 유의한 결과 없음 (p < 0.05)")

# t=0 요약
t0_rows = []
for WINDOW in [5, 1]:
    if WINDOW not in RES:
        continue
    st  = RES[WINDOW]["stats"]
    n   = len(RES[WINDOW]["ar"])
    t0_rows.append({
        "윈도우" : RES[WINDOW]["label"],
        "N"      : str(n),
        "AAR(%)" : f"{st.loc[0,'AAR']:+.4f}",
        "t_BMP"  : f"{st.loc[0,'t_bmp']:+.3f}",
        "p_BMP"  : f"{st.loc[0,'p_bmp']:.4f}",
        "부호p"  : f"{st.loc[0,'sign_p']:.4f}",
        "유의"   : "★" if st.loc[0,"sig"] else "",
    })
print_table(pd.DataFrame(t0_rows), "이벤트 당일(t=0) 요약")

# 방향 조정 요약
dir_rows = []
for WINDOW in [5, 1]:
    if WINDOW not in DIR_RES:
        continue
    dr  = DIR_RES[WINDOW]
    st  = dr["stats"]
    dir_rows.append({
        "윈도우"         : RES[WINDOW]["label"],
        "방향 유효 N"    : str(dr["n"]),
        "Dir-Adj AAR(%)": f"{st.loc[0,'AAR']:+.4f}",
        "t_BMP"          : f"{st.loc[0,'t_bmp']:+.3f}",
        "p_BMP"          : f"{st.loc[0,'p_bmp']:.4f}",
        "유의"           : "★" if st.loc[0,"sig"] else "",
    })
print_table(pd.DataFrame(dir_rows), "방향 조정(t=0) — 긍정→원화강세(DEXKOUS↓), 부정→원화약세(DEXKOUS↑) 가설")

# 오염 제외 비교
if clean_res and clean_res.get("stats") is not None:
    comp_rows = [
        {"표본": f"전체 ({n_all_c}건)",
         "AAR(t=0)": f"{ar_full_c[0].mean():+.4f}%",
         "t_BMP": f"{st_full_c.loc[0,'t_bmp']:+.3f}",
         "p": f"{st_full_c.loc[0,'p_bmp']:.4f}",
         "유의": "★" if st_full_c.loc[0,"sig"] else ""},
        {"표본": f"오염 제외 ({n_clean_c}건)",
         "AAR(t=0)": f"{ar_clean_c[0].mean():+.4f}%",
         "t_BMP": f"{st_clean_c.loc[0,'t_bmp']:+.3f}",
         "p": f"{st_clean_c.loc[0,'p_bmp']:.4f}",
         "유의": "★" if st_clean_c.loc[0,"sig"] else ""},
    ]
    print_table(pd.DataFrame(comp_rows), "전체 vs 오염 제외 비교 ([-1,+1], t=0)")
    pd.DataFrame(comp_rows).to_csv(
        os.path.join(OUT_DIR, "results_clean_compare.csv"), index=False, encoding="utf-8-sig"
    )

# Placebo 요약
if placebo is not None:
    print(f"\n  Placebo 검정 ([-5,+5]):  "
          f"실제 CAAR {placebo['actual_caar']:+.4f}%  "
          f"vs Placebo μ {placebo['sim_mean']:+.4f}%  "
          f"→ p = {placebo['p_placebo']:.4f}")

# BOK 금리 변경일 저장
if BOK_CHANGE_DATES:
    prev = bok_rate.shift(1)
    bok_rows = [{"날짜": d.date(),
                 "변경후(%)": round(bok_changes[d], 2),
                 "변경폭(%p)": round(bok_changes[d] - prev.get(d, float("nan")), 2)}
                for d in bok_changes.index]
    pd.DataFrame(bok_rows).to_csv(
        os.path.join(OUT_DIR, "bok_rate_changes.csv"), index=False, encoding="utf-8-sig"
    )

print(f"\n{'─'*55}")
print(f"완료. 결과 → {OUT_DIR}")
print(f"{'─'*55}")
