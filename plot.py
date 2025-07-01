import pandas as pd
import matplotlib.pyplot as plt

# Load the CSV that the user uploaded
path = 'eth_1m_latest_utbotv5.csv'
df = pd.read_csv(path)

# Try to detect typical column names
possible_time_cols = ['timestamp', 'date', 'datetime', 'time']
time_col = None
for col in possible_time_cols:
    if col in df.columns:
        time_col = col
        break

if time_col is None:
    raise ValueError("Couldn't find a timestamp column. Expected one of: " + ", ".join(possible_time_cols))

# Convert to datetime for nicer x-axis if not already
df[time_col] = pd.to_datetime(df[time_col])

# Detect the two series to plot.
# Standard names used in our earlier code: 'thema' for MA and 'stop' for trailing stop.
if 'thema' not in df.columns or 'stop' not in df.columns:
    raise ValueError("CSV must contain 'thema' and 'stop' columns.")

df = df.tail(200)  # Keep the last 1000 rows for plotting
# Plotting: one single figure, single axes
plt.figure(figsize=(12, 6))
plt.plot(df[time_col], df['thema'], label='Thema (MA)', linewidth=1.2, color='green')
plt.plot(df[time_col], df['stop'], label='Stop (ATR Trailing)', linewidth=1.2, color='red')
plt.legend()
plt.title("UT Bot v5 - Thema vs. Stop")
plt.xlabel("Time")
plt.ylabel("Price")
plt.tight_layout()
plt.show()
