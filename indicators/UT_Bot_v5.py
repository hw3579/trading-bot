import pandas as pd
import numpy as np
import talib as ta
from indicators.hma import hull_ma  # 你已有的 HMA 实现

def compute_ut_bot_v5(
    df: pd.DataFrame,
    allow_buy: bool = True,
    allow_sell: bool = True,
    use_heikin: bool = True,
    price_source: str = "open",
    ma_type: str = "HMA",
    ma_period: int = 2,
    atr_period: int = 11,
    a: float = 1.0,
):
    # --- 1) 生成 src --------------------------------------------------------
    if use_heikin:
        # ① 只拿 Heikin-Ashi 做 src / MA
        ha_close = (df.open + df.high + df.low + df.close) / 4
        ha_open  = [df.open.iloc[0]]
        for i in range(1, len(df)):
            ha_open.append((ha_open[-1] + ha_close.iloc[i - 1]) / 2)
        src = np.array(ha_open) if price_source == "open" else ha_close.values
    else:
        src = df[price_source].values

    # --- 2) ATR & nLoss -----------------------------------------------------
    # ⬅️ **无论是否用 Heikin，都用原始 high / low / close 来算 ATR**
    atr = ta.ATR(df.high.values, df.low.values, df.close.values,
                 timeperiod=atr_period)
    nLoss = a * atr

    # --- 3) 选 MA（src 走 Heikin / 原始都随 price_source） ------------------
    if ma_type == "SMA":
        thema = ta.SMA(src, timeperiod=ma_period)
    elif ma_type == "EMA":
        thema = ta.EMA(src, timeperiod=ma_period)
    elif ma_type == "WMA":
        thema = ta.WMA(src, timeperiod=ma_period)
    else:                               # HMA
        thema = hull_ma(src, ma_period)

    # --- 4) 逐根复刻 Trailing-Stop -----------------------------------------
    stop = np.full_like(src, np.nan)
    for i in range(len(src)):
        prev = 0 if i == 0 or np.isnan(stop[i-1]) else stop[i-1]
        cond1 = src[i] > prev
        cond2 = i > 0 and src[i] < prev and src[i-1] < prev
        cond3 = i > 0 and src[i] > prev and src[i-1] > prev

        iff1 = src[i] - nLoss[i] if cond1 else src[i] + nLoss[i]
        iff2 = min(prev, src[i] + nLoss[i]) if cond2 else iff1
        stop[i] = max(prev, src[i] - nLoss[i]) if cond3 else iff2

    # --- 5) 信号 ------------------------------------------------------------
    above = (thema[:-1] < stop[:-1]) & (thema[1:] > stop[1:])
    below = (stop[:-1] < thema[:-1]) & (stop[1:] > thema[1:])
    buy  = np.concatenate([[False], (src[1:] > stop[1:]) & above])
    sell = np.concatenate([[False], (src[1:] < stop[1:]) & below])

    if not allow_buy:
        buy[:] = False
    if not allow_sell:
        sell[:] = False

    out = df.copy()
    out["src"], out["thema"], out["stop"], out["buy"], out["sell"] = (
        src, thema, stop, buy, sell
    )
    return out

