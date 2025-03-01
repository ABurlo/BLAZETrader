import sys
import os

# Add the project root directory to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Use absolute imports from the src package
from config.config import Config
from trading.engine import TradingEngine
from visualization.trading_dashboard import TradingDashboard

# Apply nest_asyncio to allow nested event loops (needed for ib_insync in some environments)
import nest_asyncio
nest_asyncio.apply()

def main():
    # Load configuration
    config = Config()
    
    # Initialize trading engine
    engine = TradingEngine(config)
    
    # Start the trading engine
    engine.start()
    
    # Initialize and run the plotter
    plotter = TradingDashboard(engine)
    plotter.plot_dashboard()

if __name__ == "__main__":
    main()