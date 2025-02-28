from .base_plugin import PluginManager
from .technical.macd import MACDPlugin
from .technical.rsi import RSIPlugin
from .technical.williams_r import WilliamsRPlugin
from .technical.adx import ADXPlugin
from .technical.ma import MAPlugin
from .technical.stochastic import StochasticPlugin
from .technical.atr import ATRPlugin

class PluginManager(PluginManager):
    def load_plugins(self):
        self.plugins.extend([
            MACDPlugin(),
            RSIPlugin(),
            WilliamsRPlugin(),
            ADXPlugin(),
            MAPlugin(),
            StochasticPlugin(),
            ATRPlugin()
        ])