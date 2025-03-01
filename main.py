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
from src.logging.logger import TradingLogger  # Ensure this is imported

logger = TradingLogger()

async def main():
    # Initialize DataManager and TradingDashboard
    data_manager = DataManager()
    dashboard = TradingDashboard()

    try:
        # Connect to IBKR asynchronously
        logger.global_logger.info("Connecting to IBKR...")
        await dashboard.connect_to_ibkr()
        logger.global_logger.info("Connected to IBKR successfully.")

        # Fetch historical data for AMZN
        symbol = 'AMZN'
        start_date = '01/01/2024'
        end_date = '31/12/2024'
        
        # Convert dates to datetime for IBKR
        start_dt = datetime.strptime(start_date, '%d/%m/%Y')
        end_dt = datetime.strptime(end_date, '%d/%m/%Y')
        
        logger.global_logger.info(f"Fetching historical data for {symbol}...")
        df = await data_manager.fetch_historical_data_async(symbol, start_dt, end_dt)
        logger.global_logger.info(f"Data fetched for {symbol}: {df.shape if not df.empty else 'Empty DataFrame'} rows.")

        if df.empty:
            logger.global_logger.error("No data fetched for the given period. Aborting dashboard generation.")
            return

        # Add panes to the dashboard
        logger.global_logger.info("Adding panes to dashboard...")
        dashboard.add_pane('TL', 'ohlc', df, title="Price Action (OHLC)", symbol=symbol)
        dashboard.add_pane('BL', 'volume', df, title="Volume", symbol=symbol)
        dashboard.add_pane('TR', 'placeholder', df, title="Placeholder 2", symbol=symbol)
        dashboard.add_pane('BR', 'placeholder', df, title="Placeholder 3", symbol=symbol)

        # Build and display the dashboard
        logger.global_logger.info("Building and displaying dashboard...")
        await dashboard.build_dashboard(start_date, end_date, 0.00, symbol=symbol)
        logger.global_logger.info("Dashboard HTML file generated successfully.")

    except Exception as e:
        logger.global_logger.error(f"Error in dashboard generation: {str(e)}")
        raise
    finally:
        # Cancel any pending tasks and disconnect from IBKR
        pending = asyncio.all_tasks()
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        dashboard.disconnect_from_ibkr()
        logger.global_logger.info("Disconnected from IBKR and cleaned up tasks.")

def run_main():
    """Run the main coroutine, handling the event loop appropriately."""
    try:
        # Get the running event loop or create a new one
        try:
            loop = asyncio.get_running_loop()
            logger.global_logger.info("Using existing event loop...")
            # If a loop is already running (e.g., in Jupyter or IDE), schedule main() in it
            task = asyncio.ensure_future(main())
            # Keep the loop running until the task is done
            loop.run_until_complete(task)
        except RuntimeError:  # No running loop, create and run a new one
            logger.global_logger.info("Starting new event loop for main()...")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(main())
    except RuntimeError as e:
        logger.global_logger.error(f"Error in event loop: {str(e)}")
        # Fallback: Try to run in the current context or create a new loop
        try:
            # Attempt to run in the current context (e.g., Jupyter)
            task = asyncio.ensure_future(main())
            loop = asyncio.get_event_loop()
            loop.run_until_complete(task)
        except RuntimeError:
            logger.global_logger.warning("Falling back to new event loop creation...")
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
                logger.global_logger.info("Event loop closed successfully.")
            else:
                logger.global_logger.warning("Not closing loop due to pending tasks.")

if __name__ == "__main__":
    run_main()