import pandas as pd
from src.data.data_manager import DataManager
from src.trading.portfolio import Portfolio
from src.trading.orders import OrderManager
from src.trading.limits import TradingLimits
from src.plugins.plugin_manager import PluginManager
from src.logging.logger import TradingLogger
from typing import Optional, Tuple
import asyncio

class TradingEngine:
    def __init__(self):
        self.data_mgr = DataManager()
        self.portfolio = Portfolio()
        self.order_mgr = OrderManager(self.data_mgr.ib)
        self.limits = TradingLimits()
        self.plugins = PluginManager()
        self.logger = TradingLogger(log_dir="logs", log_level="INFO")
        self.ib = self.data_mgr.ib

    async def initialize(self) -> None:
        """Asynchronously initialize the TradingEngine by connecting to IBKR."""
        try:
            await self.data_mgr.connect()
            self.logger.log("INFO", "TradingEngine initialized and connected to IBKR", "global")
        except Exception as e:
            self.logger.log("ERROR", f"Error initializing TradingEngine: {str(e)}", "error")
            raise

    async def run_backtest(self, symbol: str, start_date: str, end_date: str, 
                          timeframe: str = "1 day") -> Tuple[pd.DataFrame, float]:
        """
        Run a backtest for the given symbol and date range.

        Args:
            symbol: Stock symbol (e.g., 'AAPL').
            start_date: Start date in 'DD/MM/YYYY' format.
            end_date: End date in 'DD/MM/YYYY' format.
            timeframe: Bar size (e.g., '1 day', '1 hour').

        Returns:
            Tuple containing (DataFrame of historical data, PNL as float).
        """
        try:
            # Reset portfolio for backtest
            self.portfolio.reset()

            # Fetch historical data asynchronously
            df = await self.data_mgr.fetch_historical_data_async(symbol, start_date, end_date, timeframe)

            if df.empty:
                self.logger.log("ERROR", f"No data fetched for backtest of {symbol}", "error")
                return pd.DataFrame(), 0.0

            # Process each row for backtesting
            for _, row in df.iterrows():
                if not self.limits.can_trade(row['date']):
                    self.logger.log("INFO", f"Skipping trade at {row['date']} due to limits", "global")
                    continue

                plugin_results = self.plugins.process(row)
                trade_executed, is_win = await self._apply_strategy(symbol, row, plugin_results, backtest=True)
                if trade_executed:
                    self.limits.update_trade_result(row['date'], is_win)
                self.portfolio.update(row['close'])

            pnl = self.portfolio.get_pnl()
            self.logger.log("INFO", f"Backtest completed for {symbol}. PNL: ${pnl:.2f}", "global")
            return df, pnl

        except Exception as e:
            self.logger.log("ERROR", f"Error running backtest for {symbol}: {str(e)}", "error")
            return pd.DataFrame(), 0.0

    async def run_realtime(self, symbol: str) -> None:
        """
        Run real-time trading for the given symbol using IBKR real-time bars.

        Args:
            symbol: Stock symbol (e.g., 'AAPL').
        """
        try:
            async def bar_callback(bars: pd.Series) -> None:
                """Callback for real-time bar updates."""
                row = pd.Series({
                    'date': bars.time,
                    'open': bars.open_,
                    'high': bars.high,
                    'low': bars.low,
                    'close': bars.close,
                    'volume': bars.volume
                })
                if self.limits.can_trade(row['date']):
                    plugin_results = self.plugins.process(row)
                    trade_executed, is_win = await self._apply_strategy(symbol, row, plugin_results, backtest=False)
                    if trade_executed:
                        self.limits.update_trade_result(row['date'], is_win)
                    self.portfolio.update(row['close'])

            # Subscribe to real-time bars asynchronously
            await self.data_mgr.req_real_time_bars(symbol, bar_callback)
            self.logger.log("INFO", f"Started real-time trading for {symbol}", "trade")

            # Keep the loop running (ib_insync handles this internally with async)
            while self.data_mgr.ib.isConnected():
                await asyncio.sleep(1)  # Poll to keep the loop alive

        except Exception as e:
            self.logger.log("ERROR", f"Error in real-time trading for {symbol}: {str(e)}", "error")
        finally:
            await self.cleanup()

    async def _apply_strategy(self, symbol: str, row: pd.Series, plugin_results: dict, 
                            backtest: bool = True) -> Tuple[bool, bool]:
        """
        Apply trading strategy based on plugin results.

        Args:
            symbol: Stock symbol.
            row: Data row (pandas Series) with OHLCV data.
            plugin_results: Dictionary of plugin signals (e.g., {'buy_signal': True}).
            backtest: Whether running in backtest mode.

        Returns:
            Tuple of (trade_executed: bool, is_win: bool).
        """
        trade_executed = False
        is_win = False

        if plugin_results.get('buy_signal'):
            order = self.order_mgr.place_market_order(symbol, 'BUY', 1.0)
            self.logger.log("INFO", f"Buy order placed for {symbol}: {order}", "trade")
            trade_executed = True
            # Simplified win/loss logic for backtest; refine for real trading
            is_win = row['close'] > row['open'] if backtest else False
        elif plugin_results.get('sell_signal'):
            order = self.order_mgr.place_market_order(symbol, 'SELL', 1.0)
            self.logger.log("INFO", f"Sell order placed for {symbol}: {order}", "trade")
            trade_executed = True
            is_win = row['close'] < row['open'] if backtest else False

        return trade_executed, is_win

    async def cleanup(self) -> None:
        """Clean up resources (e.g., disconnect from IBKR)."""
        try:
            await self.data_mgr.disconnect()
            self.logger.log("INFO", "TradingEngine cleaned up and disconnected from IBKR", "global")
        except Exception as e:
            self.logger.log("ERROR", f"Error during cleanup: {str(e)}", "error")