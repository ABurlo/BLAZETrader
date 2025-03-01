# src/main.py

import asyncio
import sys
import os
from datetime import datetime

# Add src/ to the Python path if running from outside src/
if __name__ == "__main__" and __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.visualization.trading_dashboard import TradingDashboard
from src.data.data_manager import DataManager

async def main():
    # Initialize DataManager and TradingDashboard
    data_manager = DataManager()
    dashboard = TradingDashboard()

    try:
        # Connect to IBKR asynchronously
        await dashboard.connect_to_ibkr()
        # Fetch historical data for AMZN
        symbol = 'AMZN'
        start_date = '01/01/2024'
        end_date = '31/12/2024'
        
        # Convert dates to datetime for IBKR
        start_dt = datetime.strptime(start_date, '%d/%m/%Y')
        end_dt = datetime.strptime(end_date, '%d/%m/%Y')
        
        df = data_manager.fetch_historical_data(symbol, start_dt, end_dt)

        # Add panes to the dashboard
        dashboard.add_pane('TL', 'ohlc', df, title="Price Action (OHLC)", symbol=symbol)
        dashboard.add_pane('BL', 'volume', df, title="Volume", symbol=symbol)
        dashboard.add_pane('TR', 'placeholder', df, title="Placeholder 2", symbol=symbol)
        dashboard.add_pane('BR', 'placeholder', df, title="Placeholder 3", symbol=symbol)

        # Build and display the dashboard
        await dashboard.build_dashboard(start_date, end_date, 0.00, symbol=symbol)

    finally:
        # Cancel any pending tasks and disconnect from IBKR
        pending = asyncio.all_tasks()
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        dashboard.disconnect_from_ibkr()

def run_main():
    """Run the main coroutine, handling the event loop appropriately."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If an event loop is already running (e.g., in Jupyter or an IDE), run the coroutine in the current loop
            asyncio.ensure_future(main())
        else:
            # If no event loop is running, create and run a new one
            loop.run_until_complete(main())
    except RuntimeError as e:
        print(f"Error: {e}")
        # Fallback: Create a new event loop if necessary
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    finally:
        # Only close the loop if it's not running and there are no pending tasks
        loop = asyncio.get_event_loop()
        if not loop.is_running() and not loop.is_closed():
            pending = asyncio.all_tasks(loop)
            if not pending:
                loop.close()
            else:
                print("Warning: Not closing loop due to pending tasks.")

if __name__ == "__main__":
    run_main()