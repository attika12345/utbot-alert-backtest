import vectorbt as vbt
import pandas as pd
import numpy as np
import talib
import datetime as dt
import json
import requests 
 
URL = 'https://api.binance.com/api/v3/klines'
 
intervals_to_secs = {
    '1m':60, '3m':180, '5m':300, '4h':900, '30m':1800,
    '1h':3600, '2h':7200, '4h':14400, '6h':21600, '8h':28800,
    '12h':43200, '1d':86400, '3d':259200, '1w':604800, '1M':2592000
}
 
def download_kline_data(start: dt.datetime, end: dt.datetime, ticker: str, interval: str) -> pd.DataFrame:
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    full_data = pd.DataFrame()
    
    print(f"Adatok letöltése: {ticker} {interval}")
    
    while start_ms < end_ms:
        par = {
            'symbol': ticker, 
            'interval': interval, 
            'startTime': start_ms, 
            'endTime': end_ms, 
            'limit': 1000
        }
        
        try:
            response = requests.get(URL, params=par, timeout=10)
            response.raise_for_status()
            data = pd.DataFrame(json.loads(response.text))
            
            if data.empty:
                print("Nincs több adat")
                break
                
            data.index = [dt.datetime.fromtimestamp(x/1000.0) for x in data.iloc[:, 0]]
            data = data.astype(float)
            full_data = pd.concat([full_data, data])
            
            # Következő batch kezdete (1000 candle után)
            start_ms = int(data.iloc[-1, 0]) + intervals_to_secs[interval] * 1000
            print(f"Letöltve: {len(full_data)} candle")
            
        except Exception as e:
            print(f"Hiba a letöltés során: {e}")
            break
    
    if full_data.empty:
        raise ValueError("Nem sikerült adatot letölteni!")
        
    full_data.columns = ['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume',
                         'Close_time', 'Qav', 'Num_trades', 'Taker_base_vol', 
                         'Taker_quote_vol', 'Ignore']
    
    # Duplikátumok eltávolítása
    full_data = full_data[~full_data.index.duplicated(keep='first')]
    
    return full_data

# UT Bot Parameters
SENSITIVITY = 1  # Magasabb = kevesebb fals jel
ATR_PERIOD = 10  # Hosszabb = simább jelek

# Ticker and timeframe
TICKER = "XRPUSDC"
INTERVAL = "4h"

# Backtest start/end date
START = dt.datetime(2024, 1, 1)  # Hosszabb időszak jobb eredményekhez
END = dt.datetime.now()

print("=" * 50)
print("UT Bot Backtest")
print("=" * 50)

# Get data from Binance
try:
    pd_data = download_kline_data(START, END, TICKER, INTERVAL)
    print(f"\nÖsszesen {len(pd_data)} candle letöltve")
    print(f"Időszak: {pd_data.index[0]} - {pd_data.index[-1]}")
except Exception as e:
    print(f"Hiba az adatletöltés során: {e}")
    exit()

# Compute ATR And nLoss variable
pd_data["xATR"] = talib.ATR(pd_data["High"], pd_data["Low"], pd_data["Close"], 
                             timeperiod=ATR_PERIOD)
pd_data["nLoss"] = SENSITIVITY * pd_data["xATR"]

# Drop all rows that have nan
pd_data = pd_data.dropna()
print(f"NaN sorok eltávolítása után: {len(pd_data)} candle")

if len(pd_data) < ATR_PERIOD + 10:
    print("Túl kevés adat a backtesthez!")
    exit()

# Function to compute ATRTrailingStop
def xATRTrailingStop_func(close, prev_close, prev_atr, nloss):
    if close > prev_atr and prev_close > prev_atr:
        return max(prev_atr, close - nloss)
    elif close < prev_atr and prev_close < prev_atr:
        return min(prev_atr, close + nloss)
    elif close > prev_atr:
        return close - nloss
    else:
        return close + nloss

# Filling ATRTrailingStop Variable
# Kezdő érték: első close - első nLoss
pd_data = pd_data.reset_index(drop=True)
first_atr = pd_data.loc[0, "Close"] - pd_data.loc[0, "nLoss"]
pd_data["ATRTrailingStop"] = [first_atr] + [np.nan for i in range(len(pd_data) - 1)]

print("\nATRTrailingStop számítása...")
for i in range(1, len(pd_data)):
    pd_data.loc[i, "ATRTrailingStop"] = xATRTrailingStop_func(
        pd_data.loc[i, "Close"],
        pd_data.loc[i - 1, "Close"],
        pd_data.loc[i - 1, "ATRTrailingStop"],
        pd_data.loc[i, "nLoss"],
    )

# Calculating signals
print("Jelek számítása...")
ema = vbt.MA.run(pd_data["Close"], 1, short_name='EMA', ewm=True)

pd_data["Above"] = ema.ma_crossed_above(pd_data["ATRTrailingStop"])
pd_data["Below"] = ema.ma_crossed_below(pd_data["ATRTrailingStop"])

pd_data["Buy"] = (pd_data["Close"] > pd_data["ATRTrailingStop"]) & (pd_data["Above"] == True)
pd_data["Sell"] = (pd_data["Close"] < pd_data["ATRTrailingStop"]) & (pd_data["Below"] == True)

print(f"Buy jelek száma: {pd_data['Buy'].sum()}")
print(f"Sell jelek száma: {pd_data['Sell'].sum()}")

# Run the strategy
print("\nBacktest futtatása...")

# Először ellenőrizzük a Buy & Hold teljesítményt
first_price = pd_data["Close"].iloc[0]
last_price = pd_data["Close"].iloc[-1]
buy_hold_return = ((last_price / first_price) - 1) * 100

print(f"\n📊 Alapadatok:")
print(f"Első ár: ${first_price:.4f}")
print(f"Utolsó ár: ${last_price:.4f}")
print(f"Buy & Hold return: {buy_hold_return:.2f}%")

pf = vbt.Portfolio.from_signals(
    pd_data["Close"],
    entries=pd_data["Buy"],
    exits=pd_data["Sell"],  # CSAK LONG! Nem short_entries
    freq="4h"  # 15 perces timeframe!
)

print("\n" + "=" * 50)
print("EREDMÉNYEK")
print("=" * 50)
print(pf.stats())