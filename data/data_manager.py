from ib_insync import IB, BarDataList
import pandas as pd
from src.config import Config

class DataManager:
    def __init__(self):
        self.ib = IB()
        self.ib.connect('127.0.0.1', 7497, clientId=1)  # Adjust port as needed
        
    def fetch_historical_data(self, symbol, start_date, end_date, timeframe="1 day"):
        contract = Stock(symbol, 'SMART', 'USD')
        bars = self.ib.reqHistoricalData(
            contract,
            endDateTime=end_date,
            durationStr=f"{(end_date - start_date).days} D",
            barSizeSetting=timeframe,
            whatToShow='TRADES',
            useRTH=True,
            formatDate=1
        )
        return self._bars_to_df(bars)
    
    def _bars_to_df(self, bars: BarDataList) -> pd.DataFrame:
        return pd.DataFrame({
            'date': [b.date for b in bars],
            'open': [b.open for b in bars],
            'high': [b.high for b in bars],
            'low': [b.low for b in bars],
            'close': [b.close for b in bars],
            'volume': [b.volume for b in bars]
        })