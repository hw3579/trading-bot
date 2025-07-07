"""
plot_ohlcv.py
示例依赖：
  pip install pandas mplfinance
用法：
  python plot_ohlcv.py path/to/your_data.csv
"""

import sys
from pathlib import Path

import pandas as pd
import mplfinance as mpf


def load_csv(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df['Date'] = pd.to_datetime(df['datetime'], utc=True)  # 加了这行
    df['Date'] = df['Date'].dt.tz_convert(None)        # 加了这行，去掉时区
    df.set_index('Date', inplace=True)
    return df


def plot_ohlcv(df: pd.DataFrame, title: str = "OHLCV Chart"):
    """
    画蜡烛图 + 成交量。可通过 mpf.make_addplot() 叠加自定义指标。
    """
    mpf.plot(
        df,
        type="candle",        # 蜡烛图
        volume=True,          # 画成交量子图
        style="charles",      # 经典黑底白烛；可改 "yahoo" / "binance" …
        title=title,
        mav=(5, 10, 20),      # 叠加 3 条均线示例；不需要就删掉
        figsize=(12, 6),
        tight_layout=True
    )


if __name__ == "__main__":
    # if len(sys.argv) != 2:
    #     sys.exit("用法: python plot_ohlcv.py path/to/your_data.csv")

    # csv_file = Path(sys.argv[1]).expanduser().resolve()
    csv_file = "./hyperliquid/data_utbot/ETH/eth_3m_latest_utbotv5.csv"
    # if not csv_file.exists():
    #     sys.exit(f"文件不存在: {csv_file}")

    data = load_csv(csv_file)
    plot_ohlcv(data, title="csv_file.stem")
