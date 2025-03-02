import pandas as pd

class EMACrossoverPlugin:
    def __init__(self, short=9, medium=20, long=200):
        self.short = short
        self.medium = medium
        self.long = long

    def process(self, data):
        # Ensure data has enough rows for EMA calculation
        if isinstance(data, pd.Series):
            return {'buy_signal': False, 'sell_signal': False}  # Not enough data yet
        
        # Calculate EMAs
        df = data.copy()
        df['EMA_short'] = df['close'].ewm(span=self.short, adjust=False).mean()
        df['EMA_medium'] = df['close'].ewm(span=self.medium, adjust=False).mean()
        df['EMA_long'] = df['close'].ewm(span=self.long, adjust=False).mean()

        # Get current and previous rows
        curr = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else None

        if prev is None:
            return {'buy_signal': False, 'sell_signal': False}

        # Buy: Short EMA crosses above Medium EMA, both above Long EMA
        buy_signal = (prev['EMA_short'] < prev['EMA_medium'] and 
                      curr['EMA_short'] >= curr['EMA_medium'] and 
                      curr['EMA_medium'] > curr['EMA_long'])

        # Sell: Short EMA crosses below Medium EMA
        sell_signal = (prev['EMA_short'] > prev['EMA_medium'] and 
                       curr['EMA_short'] <= curr['EMA_medium'])

        return {'buy_signal': buy_signal, 'sell_signal': sell_signal}