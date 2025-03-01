from datetime import datetime, timedelta
from src.config.config import Config

class TradingLimits:
    def __init__(self):
        self.no_trade_window = Config.NO_TRADE_WINDOW
        self.max_consecutive_losses = Config.MAX_CONSECUTIVE_LOSSES
        self.min_daily_win_rate = Config.MIN_DAILY_WIN_RATE
        self.daily_trades = {}
        self.consecutive_losses = 0
        
    def can_trade(self, timestamp):
        trade_date = timestamp.date() if isinstance(timestamp, datetime) else timestamp
        
        if isinstance(timestamp, datetime):
            market_open = timestamp.replace(hour=9, minute=30)
            market_close = timestamp.replace(hour=16, minute=0)
            if (timestamp < market_open + timedelta(minutes=self.no_trade_window) or
                timestamp > market_close - timedelta(minutes=self.no_trade_window)):
                return False
        
        if trade_date not in self.daily_trades:
            self.daily_trades[trade_date] = {'wins': 0, 'losses': 0, 'trades': []}
        
        if self.consecutive_losses >= self.max_consecutive_losses:
            return False
        
        daily_stats = self.daily_trades[trade_date]
        if len(daily_stats['trades']) >= 5:
            total_trades = daily_stats['wins'] + daily_stats['losses']
            win_rate = daily_stats['wins'] / total_trades if total_trades > 0 else 0
            if win_rate < self.min_daily_win_rate:
                return False
        
        return True
    
    def update_trade_result(self, timestamp, is_win):
        trade_date = timestamp.date() if isinstance(timestamp, datetime) else timestamp
        if trade_date not in self.daily_trades:
            self.daily_trades[trade_date] = {'wins': 0, 'losses': 0, 'trades': []}
        
        daily_stats = self.daily_trades[trade_date]
        daily_stats['trades'].append(is_win)
        if is_win:
            daily_stats['wins'] += 1
            self.consecutive_losses = 0
        else:
            daily_stats['losses'] += 1
            self.consecutive_losses += 1