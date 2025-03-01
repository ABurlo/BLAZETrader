from datetime import datetime

class Config:
    BROKER = "IBKR"
    TIMEZONE = "US/Eastern"
    PLUGINS_ENABLED = True
    DATA_DIR = "data_cache"
    LOG_DIR = "logs"
    
    # Trading limits
    NO_TRADE_WINDOW = 30  # minutes before/after market open/close
    MAX_CONSECUTIVE_LOSSES = 5
    MIN_DAILY_WIN_RATE = 0.51
    
    @staticmethod
    def get_date_input(prompt):
        while True:
            try:
                date_str = input(prompt)
                return datetime.strptime(date_str, "%d/%m/%Y")
            except ValueError:
                print("Invalid format. Use DD/MM/YYYY")