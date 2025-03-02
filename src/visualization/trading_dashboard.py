import os
from ib_insync import IB, Stock, util
import pandas as pd
import plotly.graph_objects as go
import datetime
from quart import Quart, render_template, request, Response

# Use an absolute path for the static folder
app = Quart(__name__, static_url_path='/static')
app.static_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), 'static'))

# Debug: Verify the static file exists
plotly_js_path = os.path.join(app.static_folder, 'plotly-2.32.0.min.js')
print(f"Checking for Plotly.js at: {plotly_js_path}")
if not os.path.exists(plotly_js_path):
    print(f"Error: Plotly.js file not found at {plotly_js_path}")
else:
    print("Plotly.js file found successfully")

class MarketDataVisualizer:
    def __init__(self, ticker, start_date, end_date):
        self.ticker = ticker.upper()
        self.start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        self.ib = None
        self.df = None

    async def connect_to_ib(self):
        """Connect to Interactive Brokers using ib_insync."""
        self.ib = IB()
        try:
            await self.ib.connectAsync('127.0.0.1', 7497, clientId=1)
            print("Connected to Interactive Brokers TWS")
        except Exception as e:
            print(f"Connection error: {e}")
            self.ib = None
            raise ConnectionError(f"Failed to connect to IBKR: {e}")

    async def fetch_historical_data(self):
        """Fetch historical market data from IB TWS."""
        try:
            if self.ib is None or not self.ib.isConnected():
                await self.connect_to_ib()
            
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
                raise ValueError(f"No data received for {self.ticker}")
            
            self.df = util.df(bars)
            print(f"Data fetched successfully. Rows: {len(self.df)}, Columns: {self.df.columns.tolist()}")
            required_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
            if not all(col in self.df.columns for col in required_columns):
                raise ValueError(f"Missing required columns: {self.df.columns.tolist()}")
            
            self.df.set_index('date', inplace=True)
            self.df.index = pd.to_datetime(self.df.index)
            return self.df
            
        except Exception as e:
            print(f"Error fetching data: {e}")
            raise
        finally:
            if self.ib and self.ib.isConnected():
                print("Disconnecting from IBKR")
                self.ib.disconnect()

    async def create_interactive_chart(self):
        """Create an interactive candlestick chart with volume."""
        try:
            df = await self.fetch_historical_data()
            if df is None or df.empty:
                error_msg = f"No data available for {self.ticker} from {self.start_date.date()} to {self.end_date.date()}"
                print(error_msg)
                return f"<div style='color: red; text-align: center;'>{error_msg}</div>"

            print(f"Creating chart for {self.ticker} with {len(df)} data points")
            candlestick = go.Candlestick(
                x=df.index,
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='Price',
                increasing_line_color='green',
                decreasing_line_color='red'
            )

            volume_colors = ['green' if (df['close'] > df['open']).iloc[i] else 'red' 
                             for i in range(len(df))]
            
            volume = go.Bar(
                x=df.index,
                y=df['volume'],
                name='Volume',
                marker_color=volume_colors,
                opacity=0.6
            )

            layout = go.Layout(
                title=f'{self.ticker} Price and Volume from {self.start_date.date()} to {self.end_date.date()}',
                yaxis_title='Price',
                xaxis_title='Date',
                template='plotly_white',
                yaxis=dict(domain=[0.3, 1.0]),
                yaxis2=dict(title='Volume', domain=[0, 0.2], overlaying='y', side='right'),
                height=800
            )

            fig = go.Figure(data=[candlestick, volume], layout=layout)
            chart_html = fig.to_html(full_html=False)
            print(f"Chart HTML generated. Length: {len(chart_html)}")
            print(f"Chart HTML snippet: {chart_html[:500]}...")
            return chart_html

        except Exception as e:
            error_msg = f"Error generating chart: {str(e)}"
            print(error_msg)
            return f"<div style='color: red; text-align: center;'>{error_msg}</div>"

@app.route('/')
async def index():
    return await render_template('index.html', ticker="AAPL", start_date="2024-01-01", end_date="2024-12-31")

@app.route('/generate_chart', methods=['POST'])
async def generate_chart():
    form = await request.form
    ticker = form['ticker'].strip()
    start_date = form['start_date'].strip()
    end_date = form['end_date'].strip()

    try:
        start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        if end <= start:
            return "End date must be after start date", 400

        visualizer = MarketDataVisualizer(ticker, start_date, end_date)
        chart_html = await visualizer.create_interactive_chart()
        if chart_html is None:
            return "Chart generation failed unexpectedly", 500

        return Response(chart_html, mimetype='text/html')
    
    except ValueError as e:
        return f"Invalid date format or ticker: {str(e)}", 400
    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)