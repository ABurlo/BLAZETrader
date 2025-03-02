import os
import datetime
import logging
from quart import Quart, render_template, request, Response, jsonify
from ib_insync import IB, Stock, util
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import json
from pytz import timezone

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Quart app
app = Quart(__name__, static_url_path='/static')
app.static_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), 'static'))

# Supported TWS API bar sizes and their maximum duration strings
SUPPORTED_DURATIONS = {
    '1 min': '1 min',
    '5 mins': '5 mins',
    '15 mins': '15 mins',
    '30 mins': '30 mins',
    '1 hour': '1 hour',
    '1 day': '1 day',
    '1 week': '1 week',
    '1 month': '1 month'
}
SUPPORTED_DURATION_STRINGS = {
    '1 min': '1 D',
    '5 mins': '5 D',
    '15 mins': '10 D',
    '30 mins': '20 D',
    '1 hour': '30 D',
    '1 day': '1 Y',
    '1 week': '2 Y',
    '1 month': '5 Y'
}

# Define timedelta multipliers for each bar size (in minutes for finer granularity)
BAR_SIZE_MULTIPLIERS = {
    '1 min': 1,         # 1 minute
    '5 mins': 5,        # 5 minutes
    '15 mins': 15,      # 15 minutes
    '30 mins': 30,      # 30 minutes
    '1 hour': 60,       # 60 minutes
    '1 day': 1440,      # 24 hours * 60 minutes
    '1 week': 10080,    # 7 days * 24 hours * 60 minutes
    '1 month': 43200    # Approx 30 days * 24 hours * 60 minutes
}

class MarketDataVisualizer:
    def __init__(self, ticker, start_date=None, end_date=None, lookback_multiplier=None, bar_size='1 day'):
        self.ticker = ticker.upper()
        eastern = timezone('US/Eastern')
        
        if lookback_multiplier is not None:
            # Use lookback multiplier based on bar_size
            self.end_date = eastern.localize(datetime.datetime.now())
            multiplier = int(lookback_multiplier)
            minutes = BAR_SIZE_MULTIPLIERS[bar_size] * multiplier
            self.start_date = self.end_date - datetime.timedelta(minutes=minutes)
        else:
            # Use explicit start and end dates
            self.start_date = eastern.localize(datetime.datetime.strptime(start_date, "%Y-%m-%d"))
            self.end_date = eastern.localize(datetime.datetime.strptime(end_date, "%Y-%m-%d"))
        
        self.bar_size = bar_size
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
            
            logger.info(f"Fetching data for {self.ticker} from {self.start_date} to {self.end_date} with bar size {self.bar_size}")
            contract = Stock(self.ticker, 'SMART', 'USD')
            duration_str = SUPPORTED_DURATION_STRINGS.get(self.bar_size, '1 Y')

            # Adjust duration based on date range to avoid exceeding TWS limits
            days_diff = (self.end_date - self.start_date).days
            if self.bar_size == '1 min' and days_diff > 1:
                duration_str = f"{min(days_diff, 1)} D"
            elif self.bar_size == '5 mins' and days_diff > 5:
                duration_str = f"{min(days_diff, 5)} D"
            elif self.bar_size == '15 mins' and days_diff > 10:
                duration_str = f"{min(days_diff, 10)} D"
            elif self.bar_size == '30 mins' and days_diff > 20:
                duration_str = f"{min(days_diff, 20)} D"
            elif self.bar_size == '1 hour' and days_diff > 30:
                duration_str = f"{min(days_diff, 30)} D"
            elif self.bar_size == '1 day' and days_diff > 365:
                duration_str = f"{min(days_diff, 365)} D"
            elif self.bar_size == '1 week' and days_diff > 730:
                duration_str = f"{min(days_diff, 730)} D"
            elif self.bar_size == '1 month' and days_diff > 1825:
                duration_str = f"{min(days_diff, 1825)} D"

            bars = await self.ib.reqHistoricalDataAsync(
                contract,
                endDateTime=self.end_date,
                durationStr=duration_str,
                barSizeSetting=self.bar_size,
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
            
            # Set index and ensure it's a timezone-aware DatetimeIndex
            self.df.set_index('date', inplace=True)
            self.df.index = pd.to_datetime(self.df.index)
            if self.df.index.tz is None:
                self.df.index = self.df.index.tz_localize('US/Eastern')
            else:
                self.df.index = self.df.index.tz_convert('US/Eastern')
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

            # Filter data to the requested date range
            df = df[(df.index >= self.start_date) & (df.index <= self.end_date)]
            if df.empty:
                error_msg = f"No data within the specified range for {self.ticker} from {self.start_date.date()} to {self.end_date.date()}"
                logger.error(error_msg)
                return {'error': error_msg}

            # Calculate total duration in days
            total_days = (self.end_date - self.start_date).days

            logger.info(f"Creating chart for {self.ticker} with {len(df)} data points")

            # Create candlestick trace for price
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

            # Create volume trace with colors based on price direction
            volume_colors = ['green' if (df['close'] > df['open']).iloc[i] else 'red'
                            for i in range(len(df))]
            volume = go.Bar(
                x=df.index,
                y=df['volume'],
                name='Volume',
                marker_color=volume_colors,
                opacity=0.6
            )

            # Use make_subplots to create two vertically stacked subplots
            from plotly.subplots import make_subplots
            fig = make_subplots(
                rows=2,  # Two rows: one for price, one for volume
                cols=1,  # Single column
                shared_xaxes=True,  # Share the x-axis (dates)
                vertical_spacing=0.05,  # Space between subplots
                subplot_titles=('', ''),  # No subplot titles needed
                row_heights=[0.7, 0.3]  # Price subplot takes 70% height, volume 30%
            )

            # Add candlestick to the first subplot (row 1)
            fig.add_trace(candlestick, row=1, col=1)

            # Add volume to the second subplot (row 2)
            fig.add_trace(volume, row=2, col=1)

            # Update layout for the figure
            fig.update_layout(
                title=f'{self.ticker} Price and Volume from {self.start_date.date()} to {self.end_date.date()} ({self.bar_size}, {total_days} days)',
                template='plotly_white',
                height=800,
                xaxis_rangeslider_visible=False,
                showlegend=True,
                # Update y-axis for the price subplot
                yaxis1=dict(
                    title='Price',
                    side='left'
                ),
                # Update y-axis for the volume subplot
                yaxis2=dict(
                    title='Volume',
                    side='left'
                ),
                # Ensure x-axis title is only on the bottom subplot
                xaxis2=dict(
                    title='Date'
                )
            )

            # Remove x-axis title from the top subplot
            fig.update_xaxes(title_text='', row=1, col=1)

            chart_json = pio.to_json(fig)
            logger.info(f"Chart JSON generated for {self.ticker}. Length: {len(chart_json)}")
            return json.loads(chart_json)

        except Exception as e:
            error_msg = f"Error generating chart: {str(e)}"
            logger.error(error_msg)
            return {'error': error_msg}

# Routes for all pages
@app.route('/')
async def index():
    """Render the landing page."""
    return await render_template('home.html')

@app.route('/dashboard')
async def dashboard():
    """Render the dashboard with an initial chart."""
    ticker = "AAPL"
    start_date = "2024-01-01"
    end_date = "2024-12-31"
    bar_size = "1 day"
    visualizer = MarketDataVisualizer(ticker, start_date=start_date, end_date=end_date, bar_size=bar_size)
    chart_json = await visualizer.create_interactive_chart()
    chart_html = go.Figure(chart_json).to_html(full_html=False, include_plotlyjs='cdn', div_id="chart-1") if 'error' not in chart_json else f"<div style='color: red; text-align: center;'>{chart_json['error']}</div>"
    return await render_template(
        'dashboard.html',
        chart_html=chart_html,
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        lookback_multiplier='',
        bar_sizes=SUPPORTED_DURATIONS.keys(),
        selected_bar_size=bar_size
    )

@app.route('/strategies')
async def strategies():
    """Render the strategies page."""
    return await render_template('strategies.html')

@app.route('/portfolio')
async def portfolio():
    """Render the portfolio page."""
    return await render_template('portfolio.html')

@app.route('/backtest')
async def backtest():
    """Render the backtest page."""
    return await render_template('backtest.html')

@app.route('/settings')
async def settings():
    """Render the settings page."""
    return await render_template('settings.html')

@app.route('/logs')
async def logs():
    """Render the logs page."""
    return await render_template('logs.html')

@app.route('/generate_chart', methods=['POST'])
async def generate_chart():
    """Handle chart generation requests from the frontend and return JSON."""
    form = await request.form
    ticker = form['ticker'].strip()
    start_date = form.get('start_date', '').strip()
    end_date = form.get('end_date', '').strip()
    lookback_multiplier = form.get('lookback_multiplier', '').strip()
    bar_size = form.get('bar_size', '1 day').strip()

    logger.info(f"Received request: ticker={ticker}, start_date={start_date}, end_date={end_date}, lookback_multiplier={lookback_multiplier}, bar_size={bar_size}")
    try:
        if lookback_multiplier:
            # Use lookback multiplier if provided
            if not lookback_multiplier.isdigit():
                raise ValueError("Lookback multiplier must be a positive integer")
            lookback_multiplier = int(lookback_multiplier)
            if lookback_multiplier <= 0:
                raise ValueError("Lookback multiplier must be greater than 0")
            visualizer = MarketDataVisualizer(ticker, lookback_multiplier=lookback_multiplier, bar_size=bar_size)
        else:
            # Use explicit dates if provided, ensure both are present
            if not (start_date and end_date):
                raise ValueError("Please provide both start date and end date, or use a lookback multiplier")
            start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.datetime.strptime(end_date, "%Y-%m-%d")
            if end <= start:
                logger.error("Validation failed: End date <= start date")
                return jsonify({'error': 'End date must be after start date'}), 400
            visualizer = MarketDataVisualizer(ticker, start_date=start_date, end_date=end_date, bar_size=bar_size)

        if bar_size not in SUPPORTED_DURATIONS:
            logger.error(f"Invalid bar size: {bar_size}")
            return jsonify({'error': f"Invalid bar size: {bar_size}"}, SUPPORTED_DURATIONS), 400

        chart_json = await visualizer.create_interactive_chart()
        if 'error' in chart_json:
            logger.error(f"Chart generation failed: {chart_json['error']}")
            return jsonify(chart_json), 400

        logger.info(f"Returning chart JSON for {ticker}")
        return jsonify(chart_json)
    
    except ValueError as e:
        logger.error(f"ValueError in generate_chart: {str(e)}")
        return jsonify({'error': f"Invalid input: {str(e)}"}), 400
    except Exception as e:
        logger.error(f"Unexpected error in generate_chart: {str(e)}", exc_info=True)
        return jsonify({'error': f"Error: {str(e)}"}), 500

if __name__ == "__main__":
    # Run the Quart app
    app.run(debug=True)