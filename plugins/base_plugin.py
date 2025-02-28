from abc import ABC, abstractmethod

class BasePlugin(ABC):
    def __init__(self, enabled=True):
        self.enabled = enabled
        
    @abstractmethod
    def process(self, data):
        """Process incoming data and return analysis results"""
        pass

class PluginManager:
    def __init__(self):
        self.plugins = []
        self.load_plugins()
        
    def load_plugins(self):
        from src.plugins.technical import candles, patterns, zones
        self.plugins.extend([
            candles.CandlePlugin(),
            patterns.PatternPlugin(),
            zones.ZonesPlugin()
        ])
        
    def process(self, data):
        results = {}
        for plugin in self.plugins:
            if plugin.enabled:
                results.update(plugin.process(data))
        return results