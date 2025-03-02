from ib_insync import IB, Stock, util
import pandas as pd
import plotly.graph_objects as go
import datetime
import os
from quart import Quart, render_template, request, send_file, Response

app = Quart(__name__)

class MarketDataVisualizer:
    def __init__(self, ticker, start_date, end_date):
        self.ticker = ticker.upper()
        self.start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        self.ib = None
        self.df = None

    async def connect_to_ib(self):
        """Connect to Interactive Brokers using ib_insync, ensuring compatibility with Quart's event loop"""
        try:
            self.ib = IB()
            await self.ib.connectAsync('127.0.0.1', 7497, clientId=1)
            print("Connected to Interactive Brokers TWS")
        except Exception as e:
            print(f"Connection error: {e}")
            self.ib = None
            raise ConnectionError(f"Failed to connect to IBKR: {e}")

    async def fetch_historical_data(self):
        """Fetch historical market data from IB TWS, ensuring proper connection handling"""
        try:
            if self.ib is None or not self.ib.isConnected():
                await self.connect_to_ib()
            
            if not self.ib.isConnected():
                raise ConnectionError("Failed to connect to Interactive Brokers TWS/Gateway")

            print(f"Fetching data for {self.ticker} from {self.start_date} to {self.end_date}")
            contract = Stock(self.ticker, 'SMART', 'USD')
            
            bars = await self.ib.reqHistoricalDataAsync(
                contract,
                endDateTime=self.end_date,
                durationStr=f'{int((self.end_date - self.start_date).days)} D',
                barSizeSetting='1 day',
                whatToShow='TRADES',
                useRTH=True
            )
            
            if not bars:
                raise ValueError(f"No data received for {self.ticker} between {self.start_date} and {self.end_date}")
            
            self.df = util.df(bars)
            print(f"Data fetched successfully. Rows: {len(self.df)}, Columns: {self.df.columns.tolist()}")
            # Validate required columns
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in self.df.columns for col in required_columns):
                raise ValueError(f"Missing required columns. Found: {self.df.columns.tolist()}")
            
            self.df.set_index('date', inplace=True)
            self.df.index = pd.to_datetime(self.df.index)
            return self.df
            
        except Exception as e:
            print(f"Error fetching data: {e}")
            return None
        finally:
            if self.ib and self.ib.isConnected():
                print("Disconnecting from IBKR")
                await self.ib.disconnect()

    async def create_interactive_chart(self):
        """Create an interactive candlestick chart with volume (green/red) in separate y-axes and return HTML"""
        await self.fetch_historical_data()
        
        if self.df is None or self.df.empty:
            error_msg = f"No data available to plot for {self.ticker} from {self.start_date.date()} to {self.end_date.date()}"
            print(error_msg)
            return f"""
            <div style="text-align: center; color: red; padding: 20px;">
                {error_msg}
            </div>
            """

        print(f"Creating chart for {self.ticker} with {len(self.df)} data points. Sample data: {self.df.head().to_dict()}")
        try:
            # Validate required columns before plotting
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in self.df.columns for col in required_columns):
                raise ValueError(f"Missing required columns for plotting. Found: {self.df.columns.tolist()}")

            # Ensure data is numeric and not NaN/None
            for col in required_columns:
                if not pd.api.types.is_numeric_dtype(self.df[col]) or self.df[col].isnull().any():
                    raise ValueError(f"Invalid or missing data in column {col}: {self.df[col].head().tolist()}")

            # Candlestick chart for price action
            candlestick = go.Candlestick(
                x=self.df.index,
                open=self.df['open'],
                high=self.df['high'],
                low=self.df['low'],
                close=self.df['close'],
                name='Price',
                increasing_line_color='green',
                decreasing_line_color='red'
            )

            # Calculate volume color (green for positive change, red for negative)
            volume_colors = ['green' if (self.df['close'] > self.df['open']).iloc[i] else 'red' 
                             for i in range(len(self.df))]
            
            # Volume bar chart with colored bars
            volume = go.Bar(
                x=self.df.index,
                y=self.df['volume'],
                name='Volume',
                marker_color=volume_colors,
                opacity=0.6
            )

            # Layout with separate y-axes and dynamic title
            layout = go.Layout(
                title=f'{self.ticker} Price and Volume (IB TWS Data) from {self.start_date.date()} to {self.end_date.date()}',
                yaxis_title='Price',
                xaxis_title='Date',
                template='plotly_white',
                yaxis=dict(domain=[0.3, 1.0]),  # Price in top 70%
                yaxis2=dict(
                    title='Volume',
                    domain=[0, 0.2],  # Volume in bottom 20%
                    overlaying='y',
                    side='right'
                ),
                height=800
            )

            # Create figure and return HTML string
            fig = go.Figure(data=[candlestick, volume], layout=layout)
            chart_html = fig.to_html(full_html=False)  # Return just the div and script for embedding
            print(f"Chart HTML generated successfully. Length: {len(chart_html)}")
            return chart_html
        except Exception as e:
            error_msg = f"Error generating chart: {str(e)}"
            print(error_msg)
            return f"""
            <div style="text-align: center; color: red; padding: 20px;">
                {error_msg}
            </div>
            """

@app.route('/')
async def index():
    """Render the initial HTML form with a two-column layout"""
    return await render_template('index.html', ticker="AAPL", start_date="2024-01-01", end_date="2024-12-31")

@app.route('/generate_chart', methods=['POST'])
async def generate_chart():
    """Generate and serve the chart based on user input"""
    ticker = (await request.form)['ticker'].strip()
    start_date = (await request.form)['start_date'].strip()
    end_date = (await request.form)['end_date'].strip()

    try:
        # Validate and parse dates
        start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        if end <= start:
            return "End date must be after start date", 400

        visualizer = MarketDataVisualizer(ticker, start_date, end_date)
        chart_html = await visualizer.create_interactive_chart()
        if chart_html is None:
            return "Unexpected error: Chart generation returned None", 500
        
        # Return the chart HTML as a response, wrapped in a full HTML document for embedding
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{ticker} Chart</title>
        </head>
        <body>
            {chart_html}
        </body>
        </html>
        """
        return Response(full_html, mimetype='text/html')
    
    except ValueError as e:
        return f"Invalid date format or ticker: {str(e)}", 400
    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)