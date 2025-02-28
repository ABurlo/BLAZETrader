import logging
from colorlog import ColoredFormatter

class TradingLogger:
    def __init__(self, log_dir="logs"):
        self.global_logger = self._setup_logger("global", f"{log_dir}/global.log", "green")
        self.error_logger = self._setup_logger("error", f"{log_dir}/errors.log", "red")
        self.trade_logger = self._setup_logger("trade", f"{log_dir}/trades.log", "blue")
        
    def _setup_logger(self, name, filename, color):
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        
        formatter = ColoredFormatter(
            f"%(log_color)s%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            log_colors={'INFO': color, 'ERROR': 'red'}
        )
        
        fh = logging.FileHandler(filename)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        return logger
    
    def log_trade(self, msg):
        self.trade_logger.info(msg)