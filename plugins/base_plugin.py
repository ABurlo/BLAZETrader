from abc import ABC, abstractmethod

class BasePlugin(ABC):
    def __init__(self, enabled=True):
        self.enabled = enabled
        
    @abstractmethod
    def process(self, data):
        pass