import pandas as pd
import asyncio
import os
from typing import Callable, Optional
from ib_insync import IB, Stock, BarDataList, RealTimeBar
from config.config import Config  # Absolute import
from logging.logger import TradingLogger  # Absolute import

class DataManager:
    def __init__(self):
        self.ib = IB()
        self.logger = TradingLogger()
        self.data_cache = {}
        self._loop = None  # Store the event loop for reference
        self.is_connected = False

    async def connect(self, timeout: int = 10) -> bool:
        """
        Asynchronously connect to IBKR with a timeout.

        Args:
            timeout: Maximum time in seconds to wait for connection.

        Returns:
            bool: True if connected, False otherwise.
        """
        try:
            # Use nest_asyncio if running in Jupyter or nested loops
            if 'jupyter' in os.environ.get('JPY_PARENT_PID', ''):
                import nest_asyncio
                nest_asyncio.apply()
                self.logger.global_logger.info("Applied nest_asyncio for Jupyter compatibility.")

            # Ensure we use the running loop or create a new one
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)

            # Attempt to connect with a timeout
            await asyncio.wait_for(self.ib.connectAsync('127.0.0.1', 7497, clientId=1), timeout=timeout)
            self.is_connected = True
            self.logger.global_logger.info("Connected to IBKR")
            return True

        except asyncio.TimeoutError:
            self.logger.global_logger.error("Timeout connecting to IBKR")
            return False
        except Exception as e:
            self.logger.global_logger.error(f"Error connecting to IBKR: {str(e)}")
            return False
        finally:
            if not self._loop.is_running():
                self._loop.close()
                self.logger.global_logger.info("Event loop closed after connection attempt.")

    async def fetch_historical_data_async(self, symbol: str, start_date: str, end_date: str, 
                                        timeframe: str = "1 day") -> pd.DataFrame:
        """
        Asynchronously fetch historical data from IBKR.

        Args:
            symbol: Stock symbol (e.g., 'AAPL').
            start_date: Start date in 'YYYYMMDD HH:MM:SS' format.
            end_date: End date in 'YYYYMMDD HH:MM:SS' format.
            timeframe: Bar size (e.g., '1 day', '1 hour').

        Returns:
            pd.DataFrame: Historical data or empty DataFrame if error occurs.
        """
        try:
            if not self.is_connected:
                if not await self.connect():
                    raise ConnectionError("Failed to connect to IBKR")

            contract = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(contract)
            
            
            bars = await self.ib.reqHistoricalDataAsync(
                contract,
                endDateTime=end_date,
                durationStr=f"{(pd.to_datetime(end_date) - pd.to_datetime(start_date)).days} D",
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
            self.logger.global_logger.info(f"Fetched historical data for {symbol}: {df.shape[0]} rows.")
            return df
        
        except Exception as e:
            self.logger.global_logger.error(f"Error fetching historical data for {symbol}: {str(e)}")
            return pd.DataFrame()

    async def req_real_time_bars(self, symbol: str, callback: Callable[[RealTimeBar], None]) -> None:
        """
        Asynchronously subscribe to real-time bars for a symbol.

        Args:
            symbol: Stock symbol (e.g., 'AAPL').
            callback: Function to handle real-time bar updates.
        """
        try:
            if not self.is_connected:
                if not await self.connect():
                    raise ConnectionError("Failed to connect to IBKR")

            contract = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(contract)

            # Use async/await with ib_insync's real-time bars
            await self.ib.reqRealTimeBarsAsync(
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
        """
        Convert IBKR BarDataList to a pandas DataFrame.

        Args:
            bars: List of BarData objects from IBKR.

        Returns:
            pd.DataFrame: DataFrame with OHLCV data.
        """
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

    async def disconnect(self) -> None:
        """Asynchronously disconnect from IBKR and clean up."""
        try:
            if self.is_connected:
                self.ib.disconnect()
                self.is_connected = False
                self.logger.global_logger.info("Disconnected from IBKR")
            if self._loop and not self._loop.is_closed():
                self._loop.close()
                self.logger.global_logger.info("Event loop closed after disconnection.")
        except Exception as e:
            self.logger.global_logger.error(f"Error disconnecting from IBKR: {str(e)}")

    def __del__(self):
        """Ensure disconnection on object deletion."""
        asyncio.run(self.disconnect()) if self.is_connected else None