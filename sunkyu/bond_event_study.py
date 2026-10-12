"""
bond_event_study.py
────────────────────────────────────────────────────────────────
만기별 미국 국채 수익률 이벤트 드리븐 백테스트
: 디지털 자산 제도화 이벤트 → 국채 가격 충격 분석

이벤트 윈도우 : [-5, +5] 영업일 (t=0: 미국 주식시장 첫 반영일)
추정 윈도우   : 이벤트 창 직전 120 영업일
표본          : Main (22건) / 전체 Main+Robust (49건)

실행 방법
    python bond_event_study.py
────────────────────────────────────────────────────────────────
"""

import os
import warnings
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from scipy import stats

warnings.filterwarnings("ignore")

# ──────────────────────────────────────────────────────────────
# 0. 경로 설정
# ──────────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "data")
OUT_DIR   = os.path.join(BASE_DIR, "output")
os.makedirs(OUT_DIR, exist_ok=True)

EVENT_XLS = os.path.join(DATA_DIR, "이벤트 리스트 제안.xlsx")
EVENT_CSV = os.path.join(DATA_DIR, "stablecoin_events.csv")

# ──────────────────────────────────────────────────────────────
# 1. FRED 국채 수익률 로드
# ──────────────────────────────────────────────────────────────
FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"
START     = "2015-01-01"

MATURITIES = {          # FRED 코드 → 표시 레이블
    "DGS1MO": "1M",
    "DGS3MO": "3M",
    "DGS6MO": "6M",
    "DGS1":   "1Y",
    "DGS2":   "2Y",
    "DGS5":   "5Y",
    "DGS10":  "10Y",
    "DGS30":  "30Y",
}

def get_fred(series_id: str, start: str = START) -> pd.Series:
    url = f"{FRED_BASE}?id={series_id}&cosd={start}"
    s = pd.read_csv(url, index_col=0, parse_dates=True, na_values=".").iloc[:, 0]
    s.name = series_id
    s.index.name = "date"
    return s

print("─" * 50)
print("FRED 국채 수익률 데이터 로딩 중...")
raw = {sid: get_fred(sid) for sid in MATURITIES}
yields = pd.DataFrame(raw)                  # 날짜 × 만기 수익률 (%)
yields = yields.ffill()                     # 주말·공휴일 결측 전진 보완
print(f"  기간: {yields.index[0].date()} ~ {yields.index[-1].date()} | {len(yields)}행")

# ──────────────────────────────────────────────────────────────
# 2. 이벤트 데이터 로드
# ──────────────────────────────────────────────────────────────
print("\n이벤트 데이터 로딩 중...")

ev_xl = pd.read_excel(EVENT_XLS, sheet_name="이벤트 리스트")
ev_xl["미국 주식 t0"] = pd.to_datetime(ev_xl["미국 주식 t0"])
ev_xl["방향"]         = pd.to_numeric(ev_xl["방향(+1/0/−1)"], errors="coerce")

ev_main   = ev_xl[ev_xl["표본"] == "Main"].copy().reset_index(drop=True)
ev_all    = ev_xl.copy().reset_index(drop=True)

print(f"  Main 표본   : {len(ev_main)}건")
print(f"  전체 표본   : {len(ev_all)}건")

# ──────────────────────────────────────────────────────────────
# 3. 이벤트 스터디 핵심 함수
# ──────────────────────────────────────────────────────────────
WINDOW  = 5    # [-5, +5]
EST_LEN = 120  # 추정 윈도우 영업일 수

def run_event_study(
    yield_series: pd.Series,
    event_df: pd.DataFrame,
    date_col: str = "미국 주식 t0",
    window: int = WINDOW,
    est_len: int = EST_LEN,
) -> tuple:
    """
    단일 만기 수익률 시리즈에 대해 이벤트 스터디를 수행합니다.

    Returns
    -------
    ar_matrix : pd.DataFrame  (n_events × (2*window+1))  비정상 수익률
    meta_list : list of dict  각 이벤트 메타 정보
    """
    dy            = yield_series.ffill().diff().dropna()   # 일간 수익률 변화 (bp 아닌 %)
    trading_days  = dy.index

    ar_rows, meta_list = [], []

    for _, row in event_df.iterrows():
        event_date = pd.Timestamp(row[date_col])

        # t0: 이벤트 날짜 이후 첫 거래일
        future = trading_days[trading_days >= event_date]
        if len(future) == 0:
            continue
        t0_date = future[0]
        t0_pos  = trading_days.get_loc(t0_date)

        # 추정 윈도우 인덱스
        est_end   = t0_pos - window - 1
        est_start = est_end - est_len
        if est_start < 0 or est_end < 1:
            continue

        est_dy = dy.iloc[est_start:est_end].dropna()
        if len(est_dy) < 30:
            continue

        mu_est    = est_dy.mean()
        sigma_est = est_dy.std(ddof=1)

        # 이벤트 윈도우 인덱스
        ev_start = t0_pos - window
        ev_end   = t0_pos + window + 1
        if ev_end > len(trading_days) or ev_start < 0:
            continue

        ev_dy = dy.iloc[ev_start:ev_end]
        if len(ev_dy) < 2 * window + 1:
            continue

        ar = (ev_dy.values - mu_est)          # 비정상 수익률 (%)

        ar_rows.append(ar)
        meta_list.append({
            "event_id"  : row.get("이벤트 ID", ""),
            "event_date": event_date,
            "t0"        : t0_date,
            "direction" : row.get("방향", np.nan),
            "category"  : row.get("카테고리", ""),
            "title"     : row.get("이벤트", ""),
            "mu_est"    : mu_est,
            "sigma_est" : sigma_est,
            "n_est"     : len(est_dy),
        })

    if not ar_rows:
        return pd.DataFrame(), []

    cols      = list(range(-window, window + 1))
    ar_matrix = pd.DataFrame(ar_rows, columns=cols)
    return ar_matrix, meta_list


def compute_stats(ar_matrix: pd.DataFrame, alpha: float = 0.05) -> pd.DataFrame:
    """
    AAR·CAAR·t-통계량·p-값 산출

    반환 DataFrame 열
        AAR      : 평균 비정상 수익률
        CAAR     : 누적 AAR
        SE       : 표준오차
        t_stat   : t-통계량
        p_value  : 양측 p-값
        sig      : 유의 여부 (p < alpha)
    """
    n    = len(ar_matrix)
    aar  = ar_matrix.mean(axis=0)
    caar = aar.cumsum()
    se   = ar_matrix.std(axis=0, ddof=1) / np.sqrt(n)
    t    = aar / se.replace(0, np.nan)
    p    = 2 * (1 - stats.t.cdf(np.abs(t).fillna(0), df=n - 1))

    return pd.DataFrame({
        "AAR"    : aar,
        "CAAR"   : caar,
        "SE"     : se,
        "t_stat" : t,
        "p_value": p,
        "sig"    : p < alpha,
    })


# ──────────────────────────────────────────────────────────────
# 4. 전체 만기에 대해 이벤트 스터디 실행
# ──────────────────────────────────────────────────────────────
print("\n이벤트 스터디 실행 중...")

results   = {}   # {sid: {"ar": ar_matrix, "meta": meta, "stats": stats_df}}
n_events  = {}   # 만기별 유효 이벤트 수

for sid, label in MATURITIES.items():
    ar_mat, meta = run_event_study(yields[sid], ev_main, date_col="미국 주식 t0")
    if ar_mat.empty:
        print(f"  {label:>4s} : 유효 이벤트 없음")
        continue
    st = compute_stats(ar_mat)
    results[sid]  = {"ar": ar_mat, "meta": meta, "stats": st, "label": label}
    n_events[sid] = len(ar_mat)
    print(f"  {label:>4s} : {len(ar_mat)}건 | "
          f"CAAR[0,+5]={ar_mat.loc[:, 0:5].sum(axis=1).mean():.4f}%  "
          f"t={st.loc[0,'t_stat']:.2f}")

# ──────────────────────────────────────────────────────────────
# 5. 방향 조정 분석 (Direction-Adjusted)
# ──────────────────────────────────────────────────────────────
# 가설: 긍정 이벤트 → 수익률 상승(+), 부정 이벤트 → 수익률 하락(-)
# → AR × direction 이 양수라면 가설 지지
print("\n방향 조정 분석 실행 중...")

dir_results = {}

for sid, label in MATURITIES.items():
    if sid not in results:
        continue
    ar_mat  = results[sid]["ar"].copy()
    meta    = results[sid]["meta"]
    dirs    = np.array([m["direction"] for m in meta])

    # direction=0 또는 NaN 제거
    valid   = ~(np.isnan(dirs) | (dirs == 0))
    ar_dir  = ar_mat.loc[valid].copy()
    d_valid = dirs[valid]

    if len(ar_dir) == 0:
        continue

    # 방향 조정: 양수 이벤트는 그대로, 음수 이벤트는 부호 반전
    ar_adj  = ar_dir.multiply(d_valid, axis=0)
    st_adj  = compute_stats(ar_adj)
    dir_results[sid] = {"ar_adj": ar_adj, "stats": st_adj, "n": len(ar_adj), "label": label}

    print(f"  {label:>4s} : 방향 유효 {len(ar_adj)}건 | "
          f"Dir-Adj CAAR[0,+5]={ar_adj.loc[:, 0:5].sum(axis=1).mean():.4f}%  "
          f"t_dir={st_adj.loc[0,'t_stat']:.2f}")

# ──────────────────────────────────────────────────────────────
# 6. 시각화
# ──────────────────────────────────────────────────────────────
print("\n차트 생성 중...")

DAYS     = list(range(-WINDOW, WINDOW + 1))
SID_LIST = [s for s in MATURITIES if s in results]
LABELS   = [results[s]["label"] for s in SID_LIST]
COLORS   = plt.cm.tab10(np.linspace(0, 1, len(SID_LIST)))

# ── 6-1. 만기별 CAAR 비교 (단일 패널)
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
fig.suptitle("만기별 국채 수익률 CAAR (디지털 자산 제도화 이벤트)", fontsize=13, fontweight="bold")

for ax, (sid_list, title) in zip(axes, [
    (SID_LIST, "원본 (Raw AR)"),
    ([s for s in SID_LIST if s in dir_results], "방향 조정 (Direction-Adjusted)"),
]):
    for i, sid in enumerate(sid_list):
        src   = results if title.startswith("원본") else dir_results
        key   = "stats" if title.startswith("원본") else "stats"
        st    = src[sid][key]
        label = results[sid]["label"]
        ax.plot(DAYS, st["CAAR"].values * 100, label=label, color=COLORS[SID_LIST.index(sid)], linewidth=1.8)
        # 95% 신뢰구간
        se_vals = src[sid]["stats"]["SE"].values * 100
        caar_v  = st["CAAR"].values * 100
        ax.fill_between(DAYS,
                         caar_v - 1.96 * np.cumsum(se_vals),
                         caar_v + 1.96 * np.cumsum(se_vals),
                         color=COLORS[SID_LIST.index(sid)], alpha=0.07)
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax.axvline(0, color="red",   linewidth=0.8, linestyle=":")
    ax.set_xlabel("이벤트 상대일 (t=0: 공개일)")
    ax.set_ylabel("CAAR (%)")
    ax.set_title(title)
    ax.legend(loc="upper left", fontsize=8, ncol=2)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(1))
    ax.grid(True, alpha=0.3)

plt.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "01_caar_by_maturity.png"), dpi=150)
plt.close()
print("  저장: 01_caar_by_maturity.png")

# ── 6-2. t-통계량 히트맵 (만기 × 상대일)
t_mat = pd.DataFrame(
    {results[sid]["label"]: results[sid]["stats"]["t_stat"].values for sid in SID_LIST},
    index=DAYS,
).T

fig, ax = plt.subplots(figsize=(13, 4))
im = ax.imshow(t_mat.values, cmap="RdBu_r", aspect="auto", vmin=-3, vmax=3)
ax.set_xticks(range(len(DAYS)))
ax.set_xticklabels([f"t{d:+d}" for d in DAYS], fontsize=9)
ax.set_yticks(range(len(LABELS)))
ax.set_yticklabels(LABELS)
ax.set_title("t-통계량 히트맵 (만기 × 이벤트 상대일)", fontsize=12, fontweight="bold")
for i in range(t_mat.shape[0]):
    for j in range(t_mat.shape[1]):
        val = t_mat.values[i, j]
        marker = "*" if abs(val) >= 1.96 else ""
        ax.text(j, i, f"{val:.2f}{marker}", ha="center", va="center",
                fontsize=7.5, color="white" if abs(val) > 2.5 else "black")
plt.colorbar(im, ax=ax, label="t-통계량")
plt.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "02_tstat_heatmap.png"), dpi=150)
plt.close()
print("  저장: 02_tstat_heatmap.png")

# ── 6-3. 이벤트 당일(t=0) 만기별 AAR 막대그래프
aar_t0   = [results[sid]["stats"].loc[0, "AAR"] * 100 for sid in SID_LIST]
sig_t0   = [results[sid]["stats"].loc[0, "sig"] for sid in SID_LIST]
bar_cols = ["#e74c3c" if s else "#95a5a6" for s in sig_t0]

fig, ax = plt.subplots(figsize=(10, 4))
bars = ax.bar(LABELS, aar_t0, color=bar_cols, edgecolor="white", linewidth=0.5)
ax.axhline(0, color="black", linewidth=0.8)
ax.set_xlabel("만기")
ax.set_ylabel("AAR t=0 (%)")
ax.set_title("이벤트 공개일 만기별 평균 비정상 수익률 (빨강=5% 유의)", fontsize=11)
for bar, val in zip(bars, aar_t0):
    ax.text(bar.get_x() + bar.get_width() / 2, val + 0.0005 * np.sign(val),
            f"{val:.4f}", ha="center", va="bottom" if val >= 0 else "top", fontsize=8)
plt.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "03_aar_t0_by_maturity.png"), dpi=150)
plt.close()
print("  저장: 03_aar_t0_by_maturity.png")

# ── 6-4. 방향별(긍정·부정) 서브그룹 CAAR — 10년물 예시
sid_10y = "DGS10"
if sid_10y in results:
    ar_10y = results[sid_10y]["ar"]
    meta_10y = results[sid_10y]["meta"]
    dirs_10y = np.array([m["direction"] for m in meta_10y])

    pos_mask = dirs_10y == 1
    neg_mask = dirs_10y == -1

    fig, ax = plt.subplots(figsize=(10, 5))
    for mask, color, lbl in [
        (pos_mask, "#2ecc71", f"긍정 이벤트 (n={pos_mask.sum()})"),
        (neg_mask, "#e74c3c", f"부정 이벤트 (n={neg_mask.sum()})"),
    ]:
        if mask.sum() == 0:
            continue
        sub_stats = compute_stats(ar_10y.loc[mask])
        caar_v = sub_stats["CAAR"].values * 100
        se_v   = sub_stats["SE"].values * 100
        ax.plot(DAYS, caar_v, label=lbl, color=color, linewidth=2)
        ax.fill_between(DAYS,
                         caar_v - 1.96 * np.cumsum(se_v),
                         caar_v + 1.96 * np.cumsum(se_v),
                         color=color, alpha=0.12)

    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax.axvline(0, color="gray",  linewidth=0.8, linestyle=":")
    ax.set_xlabel("이벤트 상대일 (t=0)")
    ax.set_ylabel("CAAR (%)")
    ax.set_title("10년물 국채 CAAR — 긍정 vs 부정 이벤트", fontsize=12, fontweight="bold")
    ax.legend(fontsize=10)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(1))
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "04_caar_10y_pos_neg.png"), dpi=150)
    plt.close()
    print("  저장: 04_caar_10y_pos_neg.png")

# ── 6-5. 카테고리별 CAAR (10년물)
if sid_10y in results:
    cats    = list(set(m["category"] for m in meta_10y if m["category"]))
    n_cats  = len(cats)
    fig, axes = plt.subplots(1, n_cats, figsize=(5 * n_cats, 4), sharey=True)
    if n_cats == 1:
        axes = [axes]

    for ax, cat in zip(axes, cats):
        cat_mask = np.array([m["category"] == cat for m in meta_10y])
        if cat_mask.sum() < 2:
            ax.set_title(f"{cat}\n(n={cat_mask.sum()}, 부족)")
            continue
        sub = compute_stats(ar_10y.loc[cat_mask])
        caar_v = sub["CAAR"].values * 100
        ax.plot(DAYS, caar_v, linewidth=2, color="#3498db")
        ax.axhline(0, color="black", linewidth=0.7, linestyle="--")
        ax.axvline(0, color="red",   linewidth=0.7, linestyle=":")
        ax.set_title(f"{cat}\n(n={cat_mask.sum()})", fontsize=10)
        ax.set_xlabel("상대일")
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_locator(mticker.MultipleLocator(2))

    axes[0].set_ylabel("CAAR (%)")
    fig.suptitle("10년물 국채 CAAR — 카테고리별", fontsize=12, fontweight="bold")
    plt.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "05_caar_10y_by_category.png"), dpi=150)
    plt.close()
    print("  저장: 05_caar_10y_by_category.png")

# ──────────────────────────────────────────────────────────────
# 7. 결과 테이블 출력 및 CSV 저장
# ──────────────────────────────────────────────────────────────
print("\n" + "─" * 60)
print("【 만기별 이벤트 창 통계 요약 (Main 표본) 】")
print("─" * 60)

summary_rows = []
for sid in SID_LIST:
    st  = results[sid]["stats"]
    lbl = results[sid]["label"]
    n   = n_events[sid]
    for day in DAYS:
        summary_rows.append({
            "만기"        : lbl,
            "FRED코드"    : sid,
            "상대일"      : day,
            "AAR(%)"      : round(st.loc[day, "AAR"] * 100, 5),
            "CAAR(%)"     : round(st.loc[day, "CAAR"] * 100, 5),
            "t_stat"      : round(st.loc[day, "t_stat"], 3),
            "p_value"     : round(st.loc[day, "p_value"], 4),
            "유의(5%)"    : "★" if st.loc[day, "sig"] else "",
            "이벤트수"    : n,
        })

summary_df = pd.DataFrame(summary_rows)
summary_df.to_csv(os.path.join(OUT_DIR, "event_study_results.csv"),
                  index=False, encoding="utf-8-sig")
print(summary_df[summary_df["유의(5%)"] == "★"].to_string(index=False))
print(f"\n전체 결과 저장: output/event_study_results.csv")

# ── 이벤트 당일(t=0) 요약 테이블
print("\n【 이벤트 당일(t=0) 요약 】")
t0_df = summary_df[summary_df["상대일"] == 0][
    ["만기", "이벤트수", "AAR(%)", "t_stat", "p_value", "유의(5%)"]
].reset_index(drop=True)
print(t0_df.to_string(index=False))

# ── 방향 조정 결과 요약
print("\n【 방향 조정(t=0) 요약 — 가설: 제도화 이벤트가 수익률에 정방향 충격 】")
dir_rows = []
for sid in [s for s in SID_LIST if s in dir_results]:
    st  = dir_results[sid]["stats"]
    lbl = results[sid]["label"]
    n   = dir_results[sid]["n"]
    dir_rows.append({
        "만기"       : lbl,
        "유효이벤트" : n,
        "Dir-Adj AAR(%)": round(st.loc[0, "AAR"] * 100, 5),
        "t_stat"     : round(st.loc[0, "t_stat"], 3),
        "p_value"    : round(st.loc[0, "p_value"], 4),
        "유의(5%)"   : "★" if st.loc[0, "sig"] else "",
    })
dir_df = pd.DataFrame(dir_rows)
print(dir_df.to_string(index=False))
dir_df.to_csv(os.path.join(OUT_DIR, "direction_adjusted_t0.csv"),
              index=False, encoding="utf-8-sig")

print("\n" + "─" * 60)
print(f"완료. 차트 및 CSV → {OUT_DIR}")
print("─" * 60)
