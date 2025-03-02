from ib_insync import IB, Stock, BarDataList, RealTimeBar
import pandas as pd
from src.config import Config
from src.logging.logger import TradingLogger

class DataManager:
    def __init__(self):
        self.ib = IB()
        self.logger = TradingLogger()
        self.data_cache = {}
    
    async def connect(self):
        """Connect to IBKR asynchronously."""
        try:
            await self.ib.connectAsync('127.0.0.1', 7497, clientId=1)
            self.logger.global_logger.info("Connected to IBKR")
        except Exception as e:
            self.logger.global_logger.error(f"Failed to connect to IBKR: {e}")
            raise
    
    def fetch_historical_data(self, symbol, start_date, end_date, timeframe="1 day"):
        """Fetch historical data synchronously (for backtesting)."""
        try:
            contract = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(contract)
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=end_date,
                durationStr=f"{(end_date - start_date).days} D",
                barSizeSetting=timeframe,
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )
            if not bars:
                raise ValueError(f"No data returned for {symbol}")
            df = self._bars_to_df(bars)
            self.data_cache[symbol] = df
            self.logger.global_logger.info(f"Fetched historical data for {symbol}")
            return df
        except Exception as e:
            self.logger.global_logger.error(f"Error fetching data for {symbol}: {e}")
            return pd.DataFrame()  # Return empty DF instead of None
    
    def req_real_time_bars(self, symbol, callback):
        """Subscribe to real-time bars."""
        contract = Stock(symbol, 'SMART', 'USD')
        self.ib.qualifyContracts(contract)
        self.ib.reqRealTimeBars(
            contract,
            5,  # 5-second bars
            'TRADES',
            True,
            callback=callback
        )
        self.logger.global_logger.info(f"Subscribed to real-time bars for {symbol}")
    
    def _bars_to_df(self, bars: BarDataList) -> pd.DataFrame:
        return pd.DataFrame({
            'date': [b.date for b in bars],
            'open': [b.open for b in bars],
            'high': [b.high for b in bars],
            'low': [b.low for b in bars],
            'close': [b.close for b in bars],
            'volume': [b.volume for b in bars]
        })