from src.plugins.base_plugin import BasePlugin
import pandas as pd
import pandas_ta as ta

class MAPlugin(BasePlugin):
    def process(self, data):
        df = pd.DataFrame([data])
        ema = ta.ema(df['close'], length=20)
        sma = ta.sma(df['close'], length=20)
        if ema is not None and sma is not None and not ema.empty:
            return {
                'ema': ema.iloc[-1],
                'sma': sma.iloc[-1],
                'buy_signal': df['close'].iloc[-1] > ema.iloc[-1],
                'sell_signal': df['close'].iloc[-1] < ema.iloc[-1]
            }
        return {}