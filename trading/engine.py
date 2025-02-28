from src.data.data_manager import DataManager
from src.trading.portfolio import Portfolio
from src.trading.orders import OrderManager
from src.trading.limits import TradingLimits
from src.plugins import PluginManager
from src.logging.logger import TradingLogger

class TradingEngine:
    def __init__(self):
        self.data_mgr = DataManager()
        self.portfolio = Portfolio()
        self.order_mgr = OrderManager(self.data_mgr.ib)
        self.limits = TradingLimits()
        self.plugins = PluginManager()
        self.logger = TradingLogger()
        
    def run_backtest(self, symbol, start_date, end_date, timeframe="1 day"):
        df = self.data_mgr.fetch_historical_data(symbol, start_date, end_date, timeframe)
        self.portfolio.reset()
        
        for i, row in df.iterrows():
            if not self.limits.can_trade(row['date']):
                self.logger.global_logger.info(f"Skipping trade at {row['date']} due to limits")
                continue
                
            plugin_results = self.plugins.process(row)
            self._apply_strategy(symbol, row, plugin_results, backtest=True)
            self.portfolio.update(row['close'])
            
        self.logger.global_logger.info(f"Backtest completed. PNL: ${self.portfolio.get_pnl():.2f}")
        return df, self.portfolio.get_pnl()
    
    def run_realtime(self, symbol):
        def bar_callback(bars: RealTimeBar):
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
                self._apply_strategy(symbol, row, plugin_results, backtest=False)
                self.portfolio.update(row['close'])
        
        self.data_mgr.req_real_time_bars(symbol, bar_callback)
        self.ib.run()  # Start IB event loop
        
    def _apply_strategy(self, symbol, row, plugin_results, backtest=True):
        # Placeholder for strategy logic (to be implemented by user)
        # Example: Use plugin results to trigger buy/sell
        if plugin_results.get('buy_signal'):
            order = self.order_mgr.place_market_order(symbol, 'BUY', 1.0)
            self.logger.trade_logger.info(f"Buy order placed: {order}")
        elif plugin_results.get('sell_signal'):
            order = self.order_mgr.place_market_order(symbol, 'SELL', 1.0)
            self.logger.trade_logger.info(f"Sell order placed: {order}")