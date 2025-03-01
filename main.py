import sys
import os
import asyncio
import nest_asyncio

# Add the src directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

# Use absolute imports from the src package
from config.config import Config
from trading.engine import TradingEngine
from visualization.trading_dashboard import Plotter

# Apply nest_asyncio to allow nested event loops (needed for ib_insync in some environments)
nest_asyncio.apply()

async def main():
    try:
        # Initialize TradingEngine and connect to IBKR
        engine = TradingEngine()
        await engine.initialize()  # Assumes TradingEngine has an async initialize method

        # Initialize Plotter
        plotter = Plotter()

        # Get user input for ticker and dates
        symbol = input("Enter ticker symbol (e.g., AAPL): ").strip().upper()
        start_date = Config.get_date_input("Enter start date (DD/MM/YYYY): ")
        end_date = Config.get_date_input("Enter end date (DD/MM/YYYY): ")

        # Run backtest and get results
        df, pnl = await engine.run_backtest(symbol, start_date, end_date, "1 day")

        # Plot the results
        plotter.plot_ohlc(df, symbol, start_date, end_date, pnl)

    except Exception as e:
        print(f"Error in main: {str(e)}")
    finally:
        # Ensure cleanup (e.g., disconnect from IBKR)
        await engine.cleanup() if hasattr(engine, 'cleanup') else None

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())