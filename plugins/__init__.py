from .base_plugin import BasePlugin

class PluginManager:
    def __init__(self):
        self.plugins = []
        self.load_plugins()
        
    def load_plugins(self):
        from .technical.macd import MACDPlugin
        from .technical.rsi import RSIPlugin
        from .technical.williams_r import WilliamsRPlugin
        from .technical.adx import ADXPlugin
        from .technical.ma import MAPlugin
        from .technical.stochastic import StochasticPlugin
        from .technical.atr import ATRPlugin
        
        self.plugins.extend([
            MACDPlugin(),
            RSIPlugin(),
            WilliamsRPlugin(),
            ADXPlugin(),
            MAPlugin(),
            StochasticPlugin(),
            ATRPlugin()
        ])
        
    def process(self, data):
        results = {}
        for plugin in self.plugins:
            if plugin.enabled:
                results.update(plugin.process(data))
        return results