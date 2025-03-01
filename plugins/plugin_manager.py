from abc import ABC, abstractmethod

class PluginManager(ABC):
    def __init__(self, enabled=True):
        self.enabled = enabled
        
    @abstractmethod
    def process(self, data):
        pass