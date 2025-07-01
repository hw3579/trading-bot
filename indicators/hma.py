# indicator_utils.py
import numpy as np
import pandas as pd

def _wma(series: pd.Series, period: int) -> pd.Series:
    """
    加权移动平均（WMA）
    权重 1,2,…,period，越新的数据权重越大。
    返回与输入等长，前 period-1 位为 NaN。
    """
    if period < 1:
        raise ValueError("period 必须 ≥ 1")
    weights = np.arange(1, period + 1)
    return series.rolling(period).apply(
        lambda x: np.dot(x, weights) / weights.sum(),
        raw=True
    )

def hull_ma(data, period: int) -> np.ndarray:
    """
    Hull Moving Average (HMA)
    公式：
        HMA(n) = WMA( 2 * WMA(price, n/2) − WMA(price, n), √n )
    参数
    ----
    data   : 可迭代序列 (list / np.ndarray / pd.Series)
    period : 整数，HMA 周期 (n)

    返回
    ----
    np.ndarray，与输入等长，前若干位为 NaN
    """
    if period < 1:
        raise ValueError("period 必须 ≥ 1")

    # 统一为 Pandas Series，便于 rolling 计算并保留索引
    price = pd.Series(data, dtype=float)

    half_len  = int(period / 2)
    sqrt_len  = int(np.sqrt(period))

    wma_half  = _wma(price, half_len)
    wma_full  = _wma(price, period)

    # 2 * WMA(n/2) − WMA(n)
    diff = 2 * wma_half - wma_full

    # 最终 HMA
    hma = _wma(diff, sqrt_len)

    return hma.to_numpy()
