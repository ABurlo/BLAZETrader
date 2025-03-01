# src/data_manager.py

from ib_insync import IB, Stock, BarDataList, RealTimeBar
import pandas as pd
import asyncio
import os
from config.config import Config
from logging.logger import TradingLogger

class DataManager:
    def __init__(self):
        self.ib = IB()
        self.logger = TradingLogger()
        self.data_cache = {}
        self._loop = None  # Store the event loop for consistency
    
    async def connect(self):
        try:
            # Use the current running loop, prioritizing Jupyter's loop
            self._loop = asyncio.get_running_loop()
            if self._loop is None or not self._loop.is_running():
                if 'jupyter' in os.environ.get('JPY_PARENT_PID', ''):
                    self.logger.global_logger.info("Using Jupyter notebook event loop for IBKR connection...")
                    self._loop = asyncio.get_event_loop()
                else:
                    self.logger.global_logger.info("Creating new event loop for IBKR connection...")
                    self._loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(self._loop)
            await self.ib.connectAsync('127.0.0.1', 7497, clientId=1)
            self.logger.global_logger.info("Connected to IBKR")
        except Exception as e:
            self.logger.global_logger.error(f"Error connecting to IBKR: {str(e)}")
            raise
    
    async def fetch_historical_data_async(self, symbol, start_date, end_date, timeframe="1 day"):
        """
        Asynchronously fetch historical data from IBKR, handling the event loop correctly.
        """
        try:
            # Ensure IBKR is connected
            if not self.ib.isConnected():
                await self.connect()

            contract = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(contract)

            # Use ib_insync's async method for historical data with the current loop
            if self._loop is None:
                self._loop = asyncio.get_running_loop() or asyncio.new_event_loop()
            
            bars = await self.ib.reqHistoricalDataAsync(
                contract,
                endDateTime=end_date,
                durationStr=f"{(end_date - start_date).days} D",
                barSizeSetting=timeframe,
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )

            if not bars:
                self.logger.global_logger.error(f"No historical data fetched for {symbol}")
                return pd.DataFrame()

            df = self._bars_to_df(bars)
            self.data_cache[symbol] = df
            self.logger.global_logger.info(f"Fetched historical data for {symbol}: {df.shape} rows.")
            return df

        except Exception as e:
            self.logger.global_logger.error(f"Error fetching historical data for {symbol}: {str(e)}")
            return pd.DataFrame()

    def req_real_time_bars(self, symbol, callback):
        try:
            if not self.ib.isConnected():
                raise ConnectionError("Not connected to IBKR. Call connect() first.")
            
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
        except Exception as e:
            self.logger.global_logger.error(f"Error subscribing to real-time bars for {symbol}: {str(e)}")

    def _bars_to_df(self, bars: BarDataList) -> pd.DataFrame:
        if not bars:
            return pd.DataFrame()
        return pd.DataFrame({
            'date': [b.date for b in bars],
            'open': [b.open for b in bars],
            'high': [b.high for b in bars],
            'low': [b.low for b in bars],
            'close': [b.close for b in bars],
            'volume': [b.volume for b in bars]
        })

    def disconnect(self):
        """Disconnect from IBKR."""
        try:
            self.ib.disconnect()
            self.logger.global_logger.info("Disconnected from IBKR")
            if self._loop and not self._loop.is_closed():
                self._loop.close()
                self.logger.global_logger.info("Event loop closed after disconnection.")
        except Exception as e:
            self.logger.global_logger.error(f"Error disconnecting from IBKR: {str(e)}")