from src.plugins.base_plugin import BasePlugin
import pandas_ta as ta

class MACDPlugin(BasePlugin):
    def process(self, data):
        df = pd.DataFrame([data])
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
        if macd is not None and not macd.empty:
            return {
                'macd': macd['MACD_12_26_9'].iloc[-1],
                'signal': macd['MACDs_12_26_9'].iloc[-1],
                'buy_signal': macd['MACD_12_26_9'].iloc[-1] > macd['MACDs_12_26_9'].iloc[-1],
                'sell_signal': macd['MACD_12_26_9'].iloc[-1] < macd['MACDs_12_26_9'].iloc[-1]
            }
        return {}