"""
Perps_backtest.py
────────────────────────────────────────────────────────────────
암호화폐 무기한선물(Perpetual Futures) 이벤트 드리븐 백테스트
: 디지털 자산 제도화 이벤트 → 펀딩 레이트·선물 수익률 충격 분석

데이터 (Binance FAPI):
  BTC 펀딩 레이트 : BTCUSDT 8시간 주기 (2019-09-13~)
  ETH 펀딩 레이트 : ETHUSDT 8시간 주기 (2019-11-07~)
  BTC 선물 수익률 : BTCUSDT 일봉 종가 (2019-09-13~)

  ※ 전체 기간 원시 데이터(8시간봉·일봉) CSV 저장
  ※ API 키 없이 공개 엔드포인트 사용 가능; 키 있으면 config에 입력

이벤트 t0    : 미국 주식 t0 (크립토 시장 24/7이나 미국장 반응 기준 통일)
이벤트 창    : [-5, +5] (메인) / [-1, +1] (보조)
추정 창      : 이벤트 전 120 거래일
오염 기준    : FOMC·CPI ±2 거래일 이내
커버리지     : 2019-09-13~ (BTC perp 출시일) — 이전 이벤트 자동 제외

방향 조정:
  긍정 이벤트 → 롱 수요 증가 → 펀딩 레이트 상승 → dir_mult = +1
  긍정 이벤트 → BTC 선물 가격 상승 → dir_mult = +1
────────────────────────────────────────────────────────────────
"""

import os, sys, re, time, unicodedata, warnings
import urllib.request, urllib.parse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.font_manager as fm
from datetime import datetime, timezone
from scipy import stats

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
try:
    from config import BINANCE_API_KEY
except (ImportError, AttributeError):
    BINANCE_API_KEY = ""

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
# 0. 경로 및 설정
# ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
OUT_DIR  = os.path.join(BASE_DIR, "output")
RAW_DIR  = os.path.join(OUT_DIR, "data")   # 원시 데이터 저장
os.makedirs(RAW_DIR, exist_ok=True)

EVENT_XLS   = os.path.join(DATA_DIR, "이벤트 리스트 제안.xlsx")
FAPI_BASE   = "https://fapi.binance.com"
EST_LEN     = 120

# Binance 데이터 커버리지 시작
SYMBOLS = {
    "BTCUSDT": {"fr_start": "2019-09-13", "price_start": "2019-09-13"},
    "ETHUSDT": {"fr_start": "2019-11-07", "price_start": "2019-11-07"},
}

# 분석 자산
ASSETS = {
    "BTC_FR" : {"symbol": "BTCUSDT", "type": "funding", "label": "BTC 펀딩레이트",  "dir_mult": +1, "color": "#f39c12"},
    "ETH_FR" : {"symbol": "ETHUSDT", "type": "funding", "label": "ETH 펀딩레이트",  "dir_mult": +1, "color": "#3498db"},
    "BTC_RET": {"symbol": "BTCUSDT", "type": "price",   "label": "BTC 선물 수익률", "dir_mult": +1, "color": "#e74c3c"},
}

# ──────────────────────────────────────────────────────────────
# 1. Binance FAPI 데이터 수집 함수
# ──────────────────────────────────────────────────────────────
def _binance_get(endpoint, params, retries=5):
    """공개 엔드포인트 요청 (API 키 있으면 헤더 추가)"""
    url = FAPI_BASE + endpoint + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    if BINANCE_API_KEY:
        req.add_header("X-MBX-APIKEY", BINANCE_API_KEY)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return __import__("json").loads(r.read())
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise RuntimeError(f"Binance FAPI 요청 실패 ({url}): {e}")


def fetch_funding_rate(symbol, start_dt, end_dt=None):
    """
    펀딩 레이트 전체 기간 수집 (페이지네이션).
    반환: DataFrame [fundingTime(UTC), fundingRate, markPrice]
    """
    if end_dt is None:
        end_dt = datetime.now(timezone.utc)
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms   = int(end_dt.timestamp()   * 1000)

    records = []
    while start_ms < end_ms:
        batch = _binance_get(
            "/fapi/v1/fundingRate",
            {"symbol": symbol, "startTime": start_ms, "limit": 1000}
        )
        if not batch:
            break
        records.extend(batch)
        last_t   = batch[-1]["fundingTime"]
        start_ms = last_t + 1
        if len(batch) < 1000:
            break
        time.sleep(0.05)

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df["fundingTime"] = pd.to_datetime(df["fundingTime"], unit="ms", utc=True)
    df["fundingRate"] = pd.to_numeric(df["fundingRate"], errors="coerce")
    df["markPrice"]   = pd.to_numeric(df["markPrice"],   errors="coerce")
    df = df.sort_values("fundingTime").reset_index(drop=True)
    return df


def fetch_klines(symbol, start_dt, end_dt=None, interval="1d"):
    """
    일봉 OHLCV 전체 기간 수집 (페이지네이션).
    반환: DataFrame [date, open, high, low, close, volume]
    """
    if end_dt is None:
        end_dt = datetime.now(timezone.utc)
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms   = int(end_dt.timestamp()   * 1000)

    candles = []
    while start_ms < end_ms:
        batch = _binance_get(
            "/fapi/v1/klines",
            {"symbol": symbol, "interval": interval,
             "startTime": start_ms, "limit": 1500}
        )
        if not batch:
            break
        candles.extend(batch)
        last_t   = batch[-1][0]
        start_ms = last_t + 1
        if len(batch) < 1500:
            break
        time.sleep(0.05)

    if not candles:
        return pd.DataFrame()

    df = pd.DataFrame(candles, columns=[
        "openTime","open","high","low","close","volume",
        "closeTime","quoteVol","numTrades","takerBase","takerQuote","ignore"
    ])
    df["date"]  = pd.to_datetime(df["openTime"], unit="ms", utc=True).dt.date.astype(str)
    for col in ["open","high","low","close","volume"]:
        df[col] = df[col].astype(float)
    return df[["date","open","high","low","close","volume"]].drop_duplicates("date")


# ──────────────────────────────────────────────────────────────
# 2. 데이터 수집 및 CSV 저장 (캐시 우선)
# ──────────────────────────────────────────────────────────────
def collect_and_cache(symbol, cfg):
    """
    이미 CSV가 있으면 로드, 없으면 Binance FAPI에서 수집 후 저장.
    반환: (funding_raw_df, funding_daily_s, price_daily_s)
    """
    fr_raw_path    = os.path.join(RAW_DIR, f"{symbol}_funding_raw.csv")
    fr_daily_path  = os.path.join(RAW_DIR, f"{symbol}_funding_daily.csv")
    price_path     = os.path.join(RAW_DIR, f"{symbol}_price_daily.csv")

    # ── 펀딩 레이트
    if os.path.exists(fr_raw_path):
        print(f"  [{symbol}] 펀딩 레이트 캐시 로드: {fr_raw_path}")
        fr_raw = pd.read_csv(fr_raw_path, parse_dates=["fundingTime"])
        fr_raw["fundingTime"] = pd.to_datetime(fr_raw["fundingTime"], format="ISO8601", utc=True)
    else:
        print(f"  [{symbol}] 펀딩 레이트 수집 중 ({cfg['fr_start']} ~ 현재)...")
        start_dt = datetime.fromisoformat(cfg["fr_start"]).replace(tzinfo=timezone.utc)
        fr_raw   = fetch_funding_rate(symbol, start_dt)
        if fr_raw.empty:
            print(f"  [{symbol}] ⚠️  펀딩 레이트 데이터 없음")
            return None, None, None
        fr_raw.to_csv(fr_raw_path, index=False)
        print(f"    → {len(fr_raw)}행 저장: {fr_raw_path}")

    # 일별 집계: 하루 내 펀딩 레이트 합산 (보통 3회/일, 고변동기 최대 6회)
    fr_raw["date"] = fr_raw["fundingTime"].dt.date.astype(str)
    fr_daily = fr_raw.groupby("date")["fundingRate"].sum() * 100  # % 단위
    fr_daily.index = pd.to_datetime(fr_daily.index)
    fr_daily.index.name = "date"
    fr_daily.name = "funding_rate_daily_pct"
    fr_daily_df = fr_daily.reset_index()
    fr_daily_df.to_csv(fr_daily_path, index=False)

    # ── 일봉 가격
    if os.path.exists(price_path):
        print(f"  [{symbol}] 가격 캐시 로드: {price_path}")
        price_df = pd.read_csv(price_path)
    else:
        print(f"  [{symbol}] 일봉 가격 수집 중 ({cfg['price_start']} ~ 현재)...")
        start_dt = datetime.fromisoformat(cfg["price_start"]).replace(tzinfo=timezone.utc)
        price_df = fetch_klines(symbol, start_dt)
        if price_df.empty:
            print(f"  [{symbol}] ⚠️  가격 데이터 없음")
            return fr_raw, fr_daily, None
        price_df.to_csv(price_path, index=False)
        print(f"    → {len(price_df)}행 저장: {price_path}")

    price_s = pd.Series(
        price_df["close"].values,
        index=pd.to_datetime(price_df["date"]),
        name="close"
    )
    price_s.index.name = "date"

    return fr_raw, fr_daily, price_s


# ──────────────────────────────────────────────────────────────
# 3. 데이터 수집 실행
# ──────────────────────────────────────────────────────────────
print("=" * 62)
print("Binance FAPI 데이터 수집")
print(f"  API 키: {'있음' if BINANCE_API_KEY else '없음 (공개 엔드포인트 사용)'}")
print("=" * 62)

collected = {}
for symbol, cfg in SYMBOLS.items():
    fr_raw, fr_daily, price_s = collect_and_cache(symbol, cfg)
    if fr_daily is not None:
        print(f"  [{symbol}] 펀딩레이트 일별: {len(fr_daily)}일  "
              f"{fr_daily.index[0].date()} ~ {fr_daily.index[-1].date()}")
    if price_s is not None:
        print(f"  [{symbol}] 일봉 가격:       {len(price_s)}일  "
              f"{price_s.index[0].date()} ~ {price_s.index[-1].date()}")
    collected[symbol] = {"fr_daily": fr_daily, "price_s": price_s}

# ──────────────────────────────────────────────────────────────
# 4. 분석 시계열 준비
# ──────────────────────────────────────────────────────────────
def make_return_series(price_s):
    """일봉 종가 → 일수익률(%)"""
    r = price_s.ffill().pct_change().dropna() * 100
    r.index.name = "date"
    return r

price_series = {}
for key, cfg in ASSETS.items():
    sym = cfg["symbol"]
    if collected[sym]["fr_daily"] is None and collected[sym]["price_s"] is None:
        print(f"  [{key}] 데이터 없음 → 건너뜀")
        continue
    if cfg["type"] == "funding":
        price_series[key] = collected[sym]["fr_daily"]
    else:
        ps = collected[sym]["price_s"]
        if ps is not None:
            price_series[key] = make_return_series(ps)

# ──────────────────────────────────────────────────────────────
# 5. 이벤트 로드
# ──────────────────────────────────────────────────────────────
print("\n이벤트 데이터 로딩...")
ev_xl = pd.read_excel(EVENT_XLS, sheet_name="이벤트 리스트")
ev_xl["미국 주식 t0"] = pd.to_datetime(ev_xl["미국 주식 t0"])
ev_xl["방향"]         = pd.to_numeric(ev_xl["방향(+1/0/−1)"], errors="coerce")

SAMPLES = {
    "Main"  : ev_xl[ev_xl["표본"] == "Main"].copy().reset_index(drop=True),
    "Robust": ev_xl[ev_xl["표본"].isin(["Main","Robust"])].copy().reset_index(drop=True),
}
print(f"  Main {len(SAMPLES['Main'])}건  /  Robust {len(SAMPLES['Robust'])}건")

# ──────────────────────────────────────────────────────────────
# 6. 오염 판정
# ──────────────────────────────────────────────────────────────
STRICT = 2

def is_contaminated(macro_text, window=STRICT):
    text = str(macro_text)
    offsets = []
    for m in re.finditer(r"(FOMC|CPI)[^(]*\(T([+\-−]?\d+)\)", text):
        try:
            offsets.append(int(m.group(2).replace("−","-")))
        except ValueError:
            pass
    if re.search(r"(FOMC|CPI)[^\n]*당일", text): offsets.append(0)
    if re.search(r"(FOMC|CPI)[^\n]*\[", text):   offsets.append(0)
    return any(abs(o) <= window for o in offsets)

# ──────────────────────────────────────────────────────────────
# 7. 이벤트 스터디
# ──────────────────────────────────────────────────────────────
def run_event_study(series, event_df, window=5):
    """
    series: 펀딩레이트(%) 또는 일수익률(%) pd.Series, index=DatetimeIndex
    반환: (AR matrix DataFrame, meta list)
    """
    trading_days = series.index
    ar_rows, meta_list = [], []

    for _, row in event_df.iterrows():
        event_date = pd.Timestamp(row["미국 주식 t0"])
        future = trading_days[trading_days >= event_date]
        if len(future) == 0:
            continue
        t0_date = future[0]
        t0_pos  = trading_days.get_loc(t0_date)

        est_end   = t0_pos - window - 1
        est_start = est_end - EST_LEN
        if est_start < 0 or est_end < 1:
            continue  # 추정 창 부족 (2019 이전 이벤트)

        est_data = series.iloc[est_start:est_end].dropna()
        if len(est_data) < 30:
            continue

        ev_start = t0_pos - window
        ev_end   = t0_pos + window + 1
        if ev_end > len(trading_days) or ev_start < 0:
            continue
        ev_data = series.iloc[ev_start:ev_end]
        if len(ev_data) < 2 * window + 1:
            continue

        ar = ev_data.values - est_data.mean()
        ar_rows.append(ar)
        meta_list.append({
            "direction"   : row.get("방향", np.nan),
            "sigma_est"   : est_data.std(ddof=1),
            "contaminated": is_contaminated(row.get("매크로 일정 겹침","—")),
        })

    cols      = list(range(-window, window+1))
    ar_matrix = pd.DataFrame(ar_rows, columns=cols) if ar_rows else pd.DataFrame(columns=cols)
    return ar_matrix, meta_list


def compute_stats(ar_matrix, meta, alpha=0.05):
    """BMP 검정 + 부호 검정, 전 날짜"""
    n    = len(ar_matrix)
    caar = 0.0
    rows = {}
    for day in ar_matrix.columns:
        ar_day = ar_matrix[day].values
        sigmas = np.array([m["sigma_est"] for m in meta])
        sigmas = np.where(sigmas < 1e-8, np.nan, sigmas)
        sar    = ar_day / sigmas
        sar_v  = sar[~np.isnan(sar)]
        caar  += np.mean(ar_day)

        if len(sar_v) < 2:
            rows[day] = dict(AAR=np.nan, CAAR=caar, t_bmp=np.nan,
                             p_bmp=np.nan, sign_p=np.nan, sig=False)
            continue

        t_bmp  = np.mean(sar_v) / (np.std(sar_v, ddof=1) / np.sqrt(len(sar_v)))
        p_bmp  = 2 * (1 - stats.t.cdf(abs(t_bmp), df=len(sar_v)-1))
        pos    = int(np.sum(ar_day > 0))
        sign_p = 2 * min(stats.binom.cdf(pos, n, 0.5),
                         1 - stats.binom.cdf(pos-1, n, 0.5))
        rows[day] = dict(AAR=np.mean(ar_day), CAAR=caar,
                         t_bmp=t_bmp, p_bmp=p_bmp, sign_p=sign_p,
                         sig=(p_bmp < alpha))

    return pd.DataFrame(rows).T


def placebo_test(ar_matrix, meta, series, window=5, n_sim=2000):
    trading_days = series.index
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
            mu  = series.iloc[ss:es].mean()
            ev  = series.iloc[t0_pos - window: t0_pos + window + 1]
            if len(ev) < 2*window+1:
                continue
            sim_cars.append((ev.values - mu).sum())
        if sim_cars:
            sim_caars.append(np.mean(sim_cars))
    sim_caars = np.array(sim_caars)
    p_up   = np.mean(sim_caars >= actual_caar)
    p_down = np.mean(sim_caars <= actual_caar)
    return dict(actual_caar=actual_caar, sim_caars=sim_caars,
                sim_mean=np.mean(sim_caars), p_placebo=2*min(p_up, p_down))

# ──────────────────────────────────────────────────────────────
# 8. 전체 실행
# ──────────────────────────────────────────────────────────────
print("\n" + "=" * 62)
print("이벤트 스터디 실행 (Main vs Robust, t0: 미국 주식 t0)")
print("=" * 62)

WINDOWS = [5, 1]
RESULTS = {}   # (key, sample_name, window)
PLACEBO = {}   # key

for key, cfg in ASSETS.items():
    if key not in price_series:
        print(f"\n── {cfg['label']}: 데이터 없음 (건너뜀)")
        continue

    s   = price_series[key]
    lbl = cfg["label"]
    print(f"\n── {lbl} ({'펀딩레이트' if cfg['type']=='funding' else '수익률'}) ──")

    for sname, ev_df in SAMPLES.items():
        for WINDOW in WINDOWS:
            ar_mat, meta = run_event_study(s, ev_df, WINDOW)
            if ar_mat.empty:
                print(f"  {sname:7s} [{WINDOW}W]: 유효 이벤트 없음")
                continue

            st     = compute_stats(ar_mat, meta)
            n_cont = sum(m["contaminated"] for m in meta)
            n_cl   = len(ar_mat) - n_cont
            cl_idx = [i for i,m in enumerate(meta) if not m["contaminated"]]
            st_cl  = compute_stats(ar_mat.iloc[cl_idx].reset_index(drop=True),
                                   [meta[i] for i in cl_idx]) if n_cl >= 5 else None

            p_cl_str = f"{st_cl.loc[0,'p_bmp']:.4f}" if st_cl is not None else "—"
            print(f"  {sname:7s} [-{WINDOW},+{WINDOW}]: "
                  f"N={len(ar_mat):2d} 오염={n_cont}  "
                  f"AAR={ar_mat[0].mean():+.5f}  "
                  f"t={st.loc[0,'t_bmp']:+.3f}  p={st.loc[0,'p_bmp']:.4f}  "
                  f"p(clean)={p_cl_str}")

            RESULTS[(key, sname, WINDOW)] = {
                "ar": ar_mat, "meta": meta, "stats": st,
                "n_clean": n_cl, "stats_clean": st_cl,
            }

    # Placebo (Main, [-5,+5])
    if (key, "Main", 5) in RESULTS and not RESULTS[(key,"Main",5)]["ar"].empty:
        pb = placebo_test(RESULTS[(key,"Main",5)]["ar"],
                          RESULTS[(key,"Main",5)]["meta"], s)
        PLACEBO[key] = pb
        print(f"  Placebo (Main): 실제={pb['actual_caar']:+.5f}  p={pb['p_placebo']:.4f}")

# ──────────────────────────────────────────────────────────────
# 9. 시각화
# ──────────────────────────────────────────────────────────────
print("\n차트 생성 중...")
DAYS5 = list(range(-5, 6))
DAYS1 = list(range(-1, 2))

# ── 차트 1: CAAR 3변수 (Main, [-5,+5])
fig, axes = plt.subplots(1, 3, figsize=(16, 5))
fig.suptitle("무기한선물 CAAR — 디지털 자산 제도화 이벤트 ([-5,+5])",
             fontsize=12, fontweight="bold")

for ax, key in zip(axes, ASSETS.keys()):
    cfg = ASSETS[key]
    for sname, ls, lw, alpha in [("Main","-",2,0.15), ("Robust","--",1.2,0.07)]:
        r = RESULTS.get((key, sname, 5))
        if r is None or r["ar"].empty:
            continue
        ar   = r["ar"]
        aar  = ar.mean(axis=0)
        caar = aar.cumsum()
        se   = ar.std(axis=0, ddof=1) / np.sqrt(len(ar))
        ax.plot(DAYS5, caar.values, ls, lw=lw, color=cfg["color"],
                label=f"{sname}(N={len(ar)})")
        ax.fill_between(DAYS5,
                        (caar - 1.96*se.cumsum()).values,
                        (caar + 1.96*se.cumsum()).values,
                        alpha=alpha, color=cfg["color"])
    ax.axhline(0, color="black", lw=0.8, linestyle="--")
    ax.axvline(0, color="gray",  lw=0.8, linestyle=":")
    unit_lbl = "펀딩 (%)" if cfg["type"] == "funding" else "%"
    ax.set_title(cfg["label"], fontsize=11)
    ax.set_xlabel("이벤트 상대일"); ax.set_ylabel(f"CAAR ({unit_lbl})")
    ax.legend(fontsize=8)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(1))
    ax.grid(True, alpha=0.3)

plt.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "01_caar_3variables.png"), dpi=150)
plt.close()
print("  저장: 01_caar_3variables.png")

# ── 차트 2: 일별 AAR 막대 (Main, [-5,+5])
fig, axes = plt.subplots(1, 3, figsize=(16, 4))
fig.suptitle("일별 평균 비정상수익률 (AAR) — Main 표본, 빨강=BMP p<0.05",
             fontsize=12, fontweight="bold")
for ax, key in zip(axes, ASSETS.keys()):
    cfg = ASSETS[key]
    r   = RESULTS.get((key, "Main", 5))
    if r is None or r["ar"].empty:
        ax.set_title(cfg["label"]); continue
    st  = r["stats"]
    aar = r["ar"].mean(axis=0)
    se  = r["ar"].std(axis=0, ddof=1) / np.sqrt(len(r["ar"]))
    bar_colors = ["#e74c3c" if st.loc[d,"sig"] else "#95a5a6" for d in DAYS5]
    ax.bar(DAYS5, aar.values, color=bar_colors, edgecolor="white", width=0.7)
    ax.errorbar(DAYS5, aar.values, yerr=1.96*se.values,
                fmt="none", color="black", capsize=4, lw=1)
    ax.axhline(0, color="black", lw=0.8)
    ax.axvline(0, color="red",   lw=0.8, linestyle=":")
    ax.set_title(cfg["label"]); ax.set_xlabel("이벤트 상대일")
    ax.xaxis.set_major_locator(mticker.MultipleLocator(1))
    ax.grid(True, alpha=0.3, axis="y")
plt.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "02_aar_by_day.png"), dpi=150)
plt.close()
print("  저장: 02_aar_by_day.png")

# ── 차트 3: BTC 펀딩레이트 긍정 vs 부정 이벤트
if ("BTC_FR", "Main", 5) in RESULTS:
    r5    = RESULTS[("BTC_FR","Main",5)]
    ar5   = r5["ar"]
    meta5 = r5["meta"]
    dirs  = np.array([m["direction"] for m in meta5])

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle("BTC 펀딩레이트 — 긍정 vs 부정 이벤트 CAAR ([-5,+5] / [-1,+1])",
                 fontsize=12, fontweight="bold")

    for ax, (ar_use, days_use) in zip(axes, [(ar5, DAYS5),
            (RESULTS.get(("BTC_FR","Main",1),{}).get("ar", pd.DataFrame()), DAYS1)]):
        if ar_use is None or ar_use.empty:
            continue
        m_use = meta5 if len(days_use) > 3 else RESULTS.get(("BTC_FR","Main",1),{}).get("meta",meta5)
        d_use = np.array([m["direction"] for m in m_use])
        for mask, color, lbl in [
            (d_use == 1,  "#27ae60", f"긍정(+1) n={int((d_use==1).sum())}"),
            (d_use == -1, "#e74c3c", f"부정(−1) n={int((d_use==-1).sum())}"),
        ]:
            if mask.sum() < 2:
                continue
            sub  = ar_use.loc[mask]
            caar = sub.mean(axis=0).cumsum()
            se   = sub.std(axis=0, ddof=1) / np.sqrt(len(sub))
            ax.plot(days_use, caar.values, lw=2, color=color, label=lbl)
            ax.fill_between(days_use,
                            (caar - 1.96*se.cumsum()).values,
                            (caar + 1.96*se.cumsum()).values,
                            alpha=0.12, color=color)
        ax.axhline(0, color="black", lw=0.8, linestyle="--")
        ax.axvline(0, color="gray",  lw=0.8, linestyle=":")
        wlbl = f"[-{(len(days_use)-1)//2},+{(len(days_use)-1)//2}]"
        ax.set_title(f"BTC 펀딩레이트  {wlbl}")
        ax.set_xlabel("이벤트 상대일"); ax.set_ylabel("CAAR (%)")
        ax.legend(fontsize=9)
        ax.xaxis.set_major_locator(mticker.MultipleLocator(1))
        ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "03_caar_pos_neg.png"), dpi=150)
    plt.close()
    print("  저장: 03_caar_pos_neg.png")

# ── 차트 4: 전체 vs 오염 제외 비교 ([-1,+1], t=0)
fig, axes = plt.subplots(1, 3, figsize=(14, 4))
fig.suptitle("전체 vs 오염 제외 — t=0 AAR (Main 표본, [-1,+1])",
             fontsize=12, fontweight="bold")
for ax, key in zip(axes, ASSETS.keys()):
    cfg = ASSETS[key]
    r   = RESULTS.get((key, "Main", 1))
    if r is None or r["ar"].empty:
        ax.set_title(cfg["label"]); continue
    n_full = len(r["ar"])
    n_cl   = r["n_clean"]
    if n_cl < 5:
        ax.set_title(cfg["label"])
        ax.text(0.5, 0.5, "clean < 5건", ha="center", va="center", transform=ax.transAxes)
        continue
    st_all = r["stats"]
    st_cl  = r["stats_clean"]
    cl_idx = [i for i,m in enumerate(r["meta"]) if not m["contaminated"]]
    ar_cl  = r["ar"].iloc[cl_idx]

    vals = [r["ar"][0].mean(), ar_cl[0].mean()]
    errs = [r["ar"][0].std(ddof=1)/np.sqrt(n_full),
            ar_cl[0].std(ddof=1)/np.sqrt(n_cl)]
    xlbls = [f"전체({n_full})", f"오염 제외({n_cl})"]
    ax.bar(xlbls, vals, color=["#5dade2","#f39c12"], alpha=0.85, edgecolor="white", width=0.5)
    ax.errorbar([0,1], vals, yerr=errs, fmt="none", color="black", capsize=5)
    ax.axhline(0, color="black", lw=0.8)
    for i, (v, e, p_) in enumerate(zip(vals, errs, [st_all.loc[0,"p_bmp"],
                                                       st_cl.loc[0,"p_bmp"] if st_cl is not None else np.nan])):
        mark = " ★" if (not np.isnan(p_) and p_ < 0.05) else ""
        ax.text(i, v + e*1.4, f"p={p_:.3f}{mark}", ha="center", fontsize=8,
                color="red" if mark else "gray")
    ax.set_title(cfg["label"]); ax.set_ylabel("AAR t=0 (%)")
    ax.grid(True, alpha=0.3, axis="y")
plt.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "04_full_vs_clean.png"), dpi=150)
plt.close()
print("  저장: 04_full_vs_clean.png")

# ── 차트 5: Placebo 분포 (3변수, Main)
fig, axes = plt.subplots(1, 3, figsize=(15, 4))
fig.suptitle("Placebo 검정 — Main 표본, 2,000회 시뮬레이션",
             fontsize=12, fontweight="bold")
for ax, key in zip(axes, ASSETS.keys()):
    cfg = ASSETS[key]
    if key not in PLACEBO:
        ax.set_title(cfg["label"]); continue
    pb  = PLACEBO[key]
    sim = pb["sim_caars"]
    ax.hist(sim, bins=50, color="#bdc3c7", edgecolor="white", alpha=0.85)
    ax.axvline(pb["actual_caar"], color=cfg["color"], lw=2,
               label=f"실제={pb['actual_caar']:+.5f}")
    ax.axvline(np.percentile(sim, 2.5),  color="navy", lw=1.2, linestyle="--")
    ax.axvline(np.percentile(sim, 97.5), color="navy", lw=1.2, linestyle="--",
               label="95% CI")
    p = pb["p_placebo"]
    ax.set_title(f"{cfg['label']}  p={p:.4f}" + (" ★" if p < 0.05 else ""))
    ax.set_xlabel("CAAR (%)"); ax.set_ylabel("빈도")
    ax.legend(fontsize=8)
plt.tight_layout()
fig.savefig(os.path.join(OUT_DIR, "05_placebo.png"), dpi=150)
plt.close()
print("  저장: 05_placebo.png")

# ──────────────────────────────────────────────────────────────
# 10. 결과 테이블 및 CSV 저장
# ──────────────────────────────────────────────────────────────
print("\n" + "=" * 62)

t0_rows = []
for key, cfg in ASSETS.items():
    for sname in ["Main","Robust"]:
        for WINDOW in WINDOWS:
            r = RESULTS.get((key, sname, WINDOW))
            if r is None or r["ar"].empty:
                continue
            st   = r["stats"]
            n    = len(r["ar"])
            n_cl = r["n_clean"]
            p_cl_str = (f"{r['stats_clean'].loc[0,'p_bmp']:.4f}"
                        if r["stats_clean"] is not None else "—")
            t0_rows.append({
                "변수"      : cfg["label"],
                "표본"      : sname,
                "윈도우"    : f"[-{WINDOW},+{WINDOW}]",
                "N"         : str(n),
                "AAR(t=0)"  : f"{r['ar'][0].mean():+.5f}",
                "t_BMP"     : f"{st.loc[0,'t_bmp']:+.3f}",
                "p(전체)"   : f"{st.loc[0,'p_bmp']:.4f}",
                "p(clean)"  : p_cl_str,
                "유의"      : "★" if st.loc[0,"sig"] else "",
            })

t0_df = pd.DataFrame(t0_rows)
print_table(t0_df, "이벤트 당일(t=0) 요약 — 전 표본·윈도우")
t0_df.to_csv(os.path.join(OUT_DIR, "results_t0_summary.csv"), index=False, encoding="utf-8-sig")

# 유의한 결과만
all_rows = []
for key, cfg in ASSETS.items():
    for sname in ["Main","Robust"]:
        r = RESULTS.get((key, sname, 5))
        if r is None or r["ar"].empty:
            continue
        st = r["stats"]
        n  = len(r["ar"])
        for day in DAYS5:
            if day not in st.index:
                continue
            all_rows.append({
                "변수": cfg["label"], "표본": sname, "상대일": f"{day:+d}",
                "N": str(n),
                "AAR": f"{st.loc[day,'AAR']:+.5f}",
                "CAAR": f"{st.loc[day,'CAAR']:+.5f}",
                "t_BMP": f"{st.loc[day,'t_bmp']:+.3f}",
                "p_BMP": f"{st.loc[day,'p_bmp']:.4f}",
                "부호p": f"{st.loc[day,'sign_p']:.4f}",
                "유의": "★" if st.loc[day,"sig"] else "",
            })
all_df = pd.DataFrame(all_rows)
all_df.to_csv(os.path.join(OUT_DIR, "results_all.csv"), index=False, encoding="utf-8-sig")

sig_df = all_df[all_df["유의"] == "★"].reset_index(drop=True)
if len(sig_df):
    print_table(sig_df.drop(columns=["유의"]), "유의한 결과 (BMP p < 0.05)")
else:
    print("\n  * 통계적으로 유의한 결과 없음 (BMP p < 0.05)")

# Placebo 요약
if PLACEBO:
    pb_rows = []
    for key, cfg in ASSETS.items():
        if key not in PLACEBO:
            continue
        pb = PLACEBO[key]
        pb_rows.append({
            "변수"      : cfg["label"],
            "실제 CAAR" : f"{pb['actual_caar']:+.5f}%",
            "Placebo μ" : f"{pb['sim_mean']:+.5f}%",
            "p_placebo" : f"{pb['p_placebo']:.4f}",
            "유의"      : "★" if pb["p_placebo"] < 0.05 else "",
        })
    print_table(pd.DataFrame(pb_rows), "Placebo 검정 (Main, [-5,+5])")

print(f"\n{'─'*62}")
print(f"  수집 데이터 저장 위치: {RAW_DIR}")
print(f"  분석 결과 저장 위치:   {OUT_DIR}")
print(f"{'─'*62}")
