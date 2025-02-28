from src.plugins.base_plugin import BasePlugin
import pandas_ta as ta

class StochasticPlugin(BasePlugin):
    def process(self, data):
        df = pd.DataFrame([data])
        stoch = ta.stoch(df['high'], df['low'], df['close'], k=14, d=3)
        if stoch is not None and not stoch.empty:
            return {
                'stoch_k': stoch['STOCHk_14_3_3'].iloc[-1],
                'stoch_d': stoch['STOCHd_14_3_3'].iloc[-1],
                'buy_signal': stoch['STOCHk_14_3_3'].iloc[-1] < 20,
                'sell_signal': stoch['STOCHk_14_3_3'].iloc[-1] > 80
            }
        return {}