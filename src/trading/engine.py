import pandas as pd
from src.data.data_manager import DataManager
from src.trading.portfolio import Portfolio
from src.trading.orders import OrderManager
from src.trading.limits import TradingLimits
from src.plugins import PluginManager, load_default_plugins
from src.logging.logger import TradingLogger

class TradingEngine:
    def __init__(self):
        self.data_mgr = DataManager()
        self.portfolio = Portfolio()
        self.order_mgr = OrderManager(self.data_mgr.ib)
        self.limits = TradingLimits()
        self.plugins = load_default_plugins()  # Load EMA crossover as default
        self.logger = TradingLogger()
        self.ib = self.data_mgr.ib
        self.trades = []  # Trade log
        self.pnl_history = []  # PNL history
    
    async def initialize(self):
        """Initialize the trading engine by connecting to IBKR."""
        try:
            await self.data_mgr.connect()
            self.logger.global_logger.info("TradingEngine initialized successfully")
        except Exception as e:
            self.logger.global_logger.error(f"Failed to initialize TradingEngine: {e}")
            raise
    
    def run_backtest(self, symbol, start_date, end_date, timeframe="1 day", initial_capital=10000):
        df = self.data_mgr.fetch_historical_data(symbol, start_date, end_date, timeframe)
        if df is None or df.empty:
            self.logger.global_logger.error(f"No data returned for {symbol}")
            return None, 0.0, [], []
        
        self.portfolio.reset(initial_capital=initial_capital)
        self.trades = []
        self.pnl_history = []

        # Process data row-by-row to avoid look-ahead bias
        for i in range(1, len(df)):
            historical_data = df.iloc[:i+1]  # Only past and current data
            row = df.iloc[i]
            
            if not self.limits.can_trade(row['date']):
                self.logger.global_logger.info(f"Skipping trade at {row['date']} due to limits")
                continue
                
            plugin_results = self.plugins.process(historical_data)
            trade_executed, is_win = self._apply_strategy(symbol, row, plugin_results, backtest=True)
            
            if trade_executed:
                self.limits.update_trade_result(row['date'], is_win)
            
            # Update portfolio and log PNL
            self.portfolio.update(row['close'])
            portfolio_value = self.portfolio.get_value(row['close'])
            self.pnl_history.append({
                'date': row['date'],
                'cash': self.portfolio.cash,
                'position_value': self.portfolio.position * row['close'],
                'total_value': portfolio_value
            })

        final_pnl = self.portfolio.get_pnl()
        self.logger.global_logger.info(f"Backtest completed. PNL: ${final_pnl:.2f}")
        return df, final_pnl, self.trades, self.pnl_history
    
    def run_realtime(self, symbol):
        def bar_callback(bars):
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
                trade_executed, is_win = self._apply_strategy(symbol, row, plugin_results, backtest=False)
                if trade_executed:
                    self.limits.update_trade_result(row['date'], is_win)
                self.portfolio.update(row['close'])
        
        self.data_mgr.req_real_time_bars(symbol, bar_callback)
        self.ib.run()
        
    def _apply_strategy(self, symbol, row, plugin_results, backtest=True):
        trade_executed = False
        is_win = False
        
        price = row['close']
        if plugin_results.get('buy_signal') and self.portfolio.cash >= price:
            shares = self.portfolio.cash // price
            cost = shares * price
            self.portfolio.cash -= cost
            self.portfolio.position += shares
            self.trades.append({
                'date': row['date'],
                'type': 'BUY',
                'price': price,
                'shares': shares
            })
            self.logger.trade_logger.info(f"Backtest BUY: {shares} shares of {symbol} at ${price}")
            trade_executed = True
            is_win = row['close'] > row['open'] if backtest else False
            
        elif plugin_results.get('sell_signal') and self.portfolio.position > 0:
            revenue = self.portfolio.position * price
            self.portfolio.cash += revenue
            shares = self.portfolio.position
            self.trades.append({
                'date': row['date'],
                'type': 'SELL',
                'price': price,
                'shares': shares
            })
            self.logger.trade_logger.info(f"Backtest SELL: {shares} shares of {symbol} at ${price}")
            self.portfolio.position = 0
            trade_executed = True
            is_win = row['close'] < row['open'] if backtest else False
        
        return trade_executed, is_win