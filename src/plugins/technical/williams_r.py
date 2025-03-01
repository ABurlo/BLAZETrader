from src.plugins.base_plugin import BasePlugin
import pandas as pd
import pandas_ta as ta

class WilliamsRPlugin(BasePlugin):
    def process(self, data):
        df = pd.DataFrame([data])
        willr = ta.willr(df['high'], df['low'], df['close'], length=14)
        if willr is not None and not willr.empty:
            return {
                'williams_r': willr.iloc[-1],
                'buy_signal': willr.iloc[-1] < -80,
                'sell_signal': willr.iloc[-1] > -20
            }
        return {}