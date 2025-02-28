from src.plugins.base_plugin import BasePlugin
import pandas as pd
import pandas_ta as ta

class RSIPlugin(BasePlugin):
    def process(self, data):
        df = pd.DataFrame([data])
        rsi = ta.rsi(df['close'], length=14)
        if rsi is not None and not rsi.empty:
            return {
                'rsi': rsi.iloc[-1],
                'buy_signal': rsi.iloc[-1] < 30,
                'sell_signal': rsi.iloc[-1] > 70
            }
        return {}