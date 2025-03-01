import pandas as pd
from ib_insync import IB, Stock, BarDataList, RealTimeBar
from config.config import Config  # Absolute import
from log.logger import TradingLogger  # Corrected import

class DataManager:
    def __init__(self):
        """
        Initialize the DataManager with configuration and logging.
        """
        self.config = Config()
        self.logger = TradingLogger()  # Initialize custom logger from src/logging/logger.py
        self.ib = None  # IB connection will be initialized as needed
        self.logger.log("INFO", "DataManager initialized", "global")

    def connect(self):
        """
        Connect to Interactive Brokers TWS or Gateway.
        """
        if self.ib is None or not self.ib.isConnected():
            try:
                self.ib = IB()
                self.ib.connect(
                    host=self.config.ib_host,
                    port=self.config.ib_port,
                    clientId=self.config.ib_client_id
                )
                self.logger.log("INFO", "Connected to Interactive Brokers", "global")
            except Exception as e:
                self.logger.log("ERROR", f"Failed to connect to IB: {str(e)}", "error")
                raise

    def disconnect(self):
        """
        Disconnect from Interactive Brokers.
        """
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            self.logger.log("INFO", "Disconnected from Interactive Brokers", "global")

    def get_historical_data(self, contract, duration: str = "1 D", bar_size: str = "1 min"):
        """
        Fetch historical data for a given contract.

        Args:
            contract: IB contract object (e.g., Stock).
            duration: Duration string (e.g., "1 D" for 1 day).
            bar_size: Bar size setting (e.g., "1 min").

        Returns:
            pd.DataFrame: Historical data as a DataFrame.
        """
        self.connect()
        try:
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime='',
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )
            if not bars:
                self.logger.log("WARNING", f"No historical data returned for {contract.symbol}", "global")
                return pd.DataFrame()
            
            # Convert BarDataList to DataFrame
            df = pd.DataFrame(
                [(bar.date, bar.open, bar.high, bar.low, bar.close, bar.volume) for bar in bars],
                columns=['date', 'open', 'high', 'low', 'close', 'volume']
            )
            df['date'] = pd.to_datetime(df['date'])
            self.logger.log("INFO", f"Fetched {len(df)} bars for {contract.symbol}", "trade")
            return df
        
        except Exception as e:
            self.logger.log("ERROR", f"Error fetching historical data: {str(e)}", "error")
            return pd.DataFrame()
        finally:
            self.disconnect()

    def get_realtime_bars(self, contract, callback):
        """
        Subscribe to real-time bars for a given contract.

        Args:
            contract: IB contract object (e.g., Stock).
            callback: Function to handle incoming RealTimeBar events.
        """
        self.connect()
        try:
            self.ib.reqRealTimeBars(
                contract,
                barSize=5,  # 5-second bars
                whatToShow='TRADES',
                useRTH=True,
                realTimeBarsOptions=[],
                callback=callback
            )
            self.logger.log("INFO", f"Subscribed to real-time bars for {contract.symbol}", "trade")
        except Exception as e:
            self.logger.log("ERROR", f"Error subscribing to real-time bars: {str(e)}", "error")
            raise

    def cancel_realtime_bars(self, contract):
        """
        Cancel real-time bar subscription for a contract.

        Args:
            contract: IB contract object.
        """
        if self.ib and self.ib.isConnected():
            self.ib.cancelRealTimeBars(contract)
            self.logger.log("INFO", f"Cancelled real-time bars for {contract.symbol}", "trade")

if __name__ == "__main__":
    # Example usage
    dm = DataManager()
    stock = Stock("AAPL", "SMART", "USD")
    df = dm.get_historical_data(stock)
    print(df.head())