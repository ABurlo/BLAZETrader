from src.plugins.base_plugin import BasePlugin
import pandas as pd
import pandas_ta as ta

class ADXPlugin(BasePlugin):
    def process(self, data):
        df = pd.DataFrame([data])
        adx = ta.adx(df['high'], df['low'], df['close'], length=14)
        if adx is not None and not adx.empty:
            return {
                'adx': adx['ADX_14'].iloc[-1],
                'trending': adx['ADX_14'].iloc[-1] > 25
            }
        return {}