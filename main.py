from src.config import Config
from src.trading.engine import TradingEngine
from src.visualization.plotter import Plotter

def main():
    engine = TradingEngine()
    plotter = Plotter()
    
    # User inputs
    symbol = input("Enter ticker symbol: ")
    start_date = Config.get_date_input("Enter start date (DD/MM/YYYY): ")
    end_date = Config.get_date_input("Enter end date (DD/MM/YYYY): ")
    
    # Run backtest
    df, pnl = engine.run_backtest(symbol, start_date, end_date, "1 day")
    
    # Plot results
    plotter.plot_ohlc(df, symbol, start_date, end_date, pnl)

if __name__ == "__main__":
    main()