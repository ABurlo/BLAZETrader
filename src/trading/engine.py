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
        self.ib = self.data_mgr.ib
    
    async def initialize(self):
        """Initialize the trading engine by connecting to IBKR."""
        try:
            await self.data_mgr.connect()
            self.logger.global_logger.info("TradingEngine initialized successfully")
        except Exception as e:
            self.logger.global_logger.error(f"Failed to initialize TradingEngine: {e}")
            raise
    
    def run_backtest(self, symbol, start_date, end_date, timeframe="1 day"):
        df = self.data_mgr.fetch_historical_data(symbol, start_date, end_date, timeframe)
        if df is None or df.empty:
            self.logger.global_logger.error(f"No data returned for {symbol}")
            return None, 0.0
        self.portfolio.reset()
        
        for i, row in df.iterrows():
            if not self.limits.can_trade(row['date']):
                self.logger.global_logger.info(f"Skipping trade at {row['date']} due to limits")
                continue
                
            plugin_results = self.plugins.process(row)
            trade_executed, is_win = self._apply_strategy(symbol, row, plugin_results, backtest=True)
            if trade_executed:
                self.limits.update_trade_result(row['date'], is_win)
            self.portfolio.update(row['close'])
            
        pnl = self.portfolio.get_pnl()
        self.logger.global_logger.info(f"Backtest completed. PNL: ${pnl:.2f}")
        return df, pnl
    
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
        
        if plugin_results.get('buy_signal'):
            order = self.order_mgr.place_market_order(symbol, 'BUY', 1.0)
            self.logger.trade_logger.info(f"Buy order placed: {order}")
            trade_executed = True
            is_win = row['close'] > row['open'] if backtest else False
        elif plugin_results.get('sell_signal'):
            order = self.order_mgr.place_market_order(symbol, 'SELL', 1.0)
            self.logger.trade_logger.info(f"Sell order placed: {order}")
            trade_executed = True
            is_win = row['close'] < row['open'] if backtest else False
        
        return trade_executed, is_win