from src.plugins.base_plugin import BasePlugin
import pandas_ta as ta

class ATRPlugin(BasePlugin):
    def process(self, data):
        df = pd.DataFrame([data])
        atr = ta.atr(df['high'], df['low'], df['close'], length=14)
        if atr is not None and not atr.empty:
            return {'atr': atr.iloc[-1]}
        return {}