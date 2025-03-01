import asyncio
import nest_asyncio
from src.config import Config
from src.trading.engine import TradingEngine
from src.visualization.plotter import Plotter

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

async def main():
    engine = TradingEngine()
    await engine.initialize()  # Connect to IBKR asynchronously
    plotter = Plotter()
    
    symbol = input("Enter ticker symbol: ")
    start_date = Config.get_date_input("Enter start date (DD/MM/YYYY): ")
    end_date = Config.get_date_input("Enter end date (DD/MM/YYYY): ")
    
    df, pnl = engine.run_backtest(symbol, start_date, end_date, "1 day")
    plotter.plot_ohlc(df, symbol, start_date, end_date, pnl)

if __name__ == "__main__":
    asyncio.run(main())