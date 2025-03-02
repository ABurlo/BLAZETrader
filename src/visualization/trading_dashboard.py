import os
import datetime
import logging
from quart import Quart, render_template, request, Response, jsonify
from ib_insync import IB, Stock, util
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Quart app
app = Quart(__name__, static_url_path='/static')
app.static_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), 'static'))

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
            await self.ib.connectAsync('127.0.0.1', 7497, clientId=10)
            logger.info("Connected to Interactive Brokers TWS")
        except Exception as e:
            logger.error(f"Connection error: {e}")
            self.ib = None
            raise ConnectionError(f"Failed to connect to IBKR: {e}")

    async def fetch_historical_data(self):
        """Fetch historical market data from IB TWS."""
        try:
            if self.ib is None or not self.ib.isConnected():
                await self.connect_to_ib()
            
            logger.info(f"Fetching data for {self.ticker} from {self.start_date} to {self.end_date}")
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
            logger.info(f"Data fetched successfully. Rows: {len(self.df)}, Columns: {self.df.columns.tolist()}")
            required_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
            if not all(col in self.df.columns for col in required_columns):
                raise ValueError(f"Missing required columns: {self.df.columns.tolist()}")
            
            self.df.set_index('date', inplace=True)
            self.df.index = pd.to_datetime(self.df.index)
            return self.df
            
        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            raise
        finally:
            if self.ib and self.ib.isConnected():
                logger.info("Disconnecting from IBKR")
                self.ib.disconnect()

    async def create_interactive_chart(self):
        """Create an interactive candlestick chart with volume and return as JSON."""
        try:
            df = await self.fetch_historical_data()
            if df is None or df.empty:
                error_msg = f"No data available for {self.ticker} from {self.start_date.date()} to {self.end_date.date()}"
                logger.error(error_msg)
                return {'error': error_msg}

            logger.info(f"Creating chart for {self.ticker} with {len(df)} data points")
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
            chart_json = pio.to_json(fig)  # Serialize to JSON string
            logger.info(f"Chart JSON generated for {self.ticker}. Length: {len(chart_json)}")
            return json.loads(chart_json)  # Convert back to dict for jsonify

        except Exception as e:
            error_msg = f"Error generating chart: {str(e)}"
            logger.error(error_msg)
            return {'error': error_msg}

@app.route('/')
async def index():
    """Render the main dashboard with an initial chart."""
    ticker = "AAPL"
    start_date = "2024-01-01"
    end_date = "2024-12-31"
    visualizer = MarketDataVisualizer(ticker, start_date, end_date)
    chart_json = await visualizer.create_interactive_chart()
    chart_html = go.Figure(chart_json).to_html(full_html=False, include_plotlyjs='cdn', div_id="chart-1") if 'error' not in chart_json else f"<div style='color: red; text-align: center;'>{chart_json['error']}</div>"
    return await render_template('ib_trading_chart.html', chart_html=chart_html, ticker=ticker, start_date=start_date, end_date=end_date)

@app.route('/generate_chart', methods=['POST'])
async def generate_chart():
    """Handle chart generation requests from the frontend and return JSON."""
    form = await request.form
    ticker = form['ticker'].strip()
    start_date = form['start_date'].strip()
    end_date = form['end_date'].strip()

    logger.info(f"Received request: ticker={ticker}, start_date={start_date}, end_date={end_date}")
    try:
        start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        if end <= start:
            logger.error("Validation failed: End date <= start date")
            return jsonify({'error': 'End date must be after start date'}), 400

        visualizer = MarketDataVisualizer(ticker, start_date, end_date)
        chart_json = await visualizer.create_interactive_chart()
        if 'error' in chart_json:
            logger.error(f"Chart generation failed: {chart_json['error']}")
            return jsonify(chart_json), 400

        logger.info(f"Returning chart JSON for {ticker}")
        return jsonify(chart_json)
    
    except ValueError as e:
        logger.error(f"ValueError in generate_chart: {str(e)}")
        return jsonify({'error': f"Invalid date format or ticker: {str(e)}"}), 400
    except Exception as e:
        logger.error(f"Unexpected error in generate_chart: {str(e)}", exc_info=True)
        return jsonify({'error': f"Error: {str(e)}"}), 500

# No if __name__ == "__main__": block; Uvicorn runs the app directly