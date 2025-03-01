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

    # Connect to IBKR asynchronously
    await dashboard.connect_to_ibkr()

    try:
        # Fetch historical data for AMZN
        symbol = 'AMZN'
        start_date = '01/01/2024'
        end_date = '31/12/2024'
        df = data_manager.fetch_historical_data(symbol, datetime.strptime(start_date, '%d/%m/%Y'), datetime.strptime(end_date, '%d/%m/%Y'))

        # Add panes to the dashboard
        dashboard.add_pane('TL', 'ohlc', df, title="Price Action (OHLC)", symbol=symbol)
        dashboard.add_pane('BL', 'volume', df, title="Volume", symbol=symbol)
        dashboard.add_pane('TR', 'placeholder', df, title="Placeholder 2", symbol=symbol)
        dashboard.add_pane('BR', 'placeholder', df, title="Placeholder 3", symbol=symbol)

        # Build and display the dashboard
        await dashboard.build_dashboard(start_date, end_date, 0.00, symbol=symbol)

    finally:
        # Disconnect from IBKR
        dashboard.disconnect_from_ibkr()

if __name__ == "__main__":
    asyncio.run(main())