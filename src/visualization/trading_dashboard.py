import os
import datetime
import logging
import numpy as np
from quart import Quart, render_template, request, Response, jsonify
from ib_insync import IB, Stock, util
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import json
from pytz import timezone
from plotly.subplots import make_subplots

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

# Define timedelta multipliers for each bar size (in minutes)
BAR_SIZE_MULTIPLIERS = {
    '1 min': 1,
    '5 mins': 5,
    '15 mins': 15,
    '30 mins': 30,
    '1 hour': 60,
    '1 day': 1440,
    '1 week': 10080,
    '1 month': 43200
}

class MarketDataVisualizer:
    def __init__(self, ticker, start_date=None, end_date=None, lookback_multiplier=None, bar_size='1 day'):
        self.ticker = ticker.upper()
        eastern = timezone('US/Eastern')
        if lookback_multiplier is not None:
            self.end_date = eastern.localize(datetime.datetime.now())
            multiplier = int(lookback_multiplier)
            minutes = BAR_SIZE_MULTIPLIERS[bar_size] * multiplier
            self.start_date = self.end_date - datetime.timedelta(minutes=minutes)
        else:
            self.start_date = eastern.localize(datetime.datetime.strptime(start_date, "%Y-%m-%d"))
            self.end_date = eastern.localize(datetime.datetime.strptime(end_date, "%Y-%m-%d"))
        self.bar_size = bar_size
        self.ib = None
        self.df = None
        self.backtest_results = None

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

    def calculate_pnl_and_trades(self):
        """Universal PNL and trade log calculation based on signals."""
        if self.df is None or self.df.empty or 'signal' not in self.df.columns:
            logger.error("No data or signals available for PNL calculation")
            return
        
        # Ensure signals are valid (1 = buy, -1 = sell, 0 = hold)
        self.df['signal'] = self.df['signal'].fillna(0)
        self.df['position'] = self.df['signal'].shift(1)  # Position held on next bar
        
        # Calculate daily returns and strategy returns
        self.df['daily_return'] = self.df['close'].pct_change()
        self.df['strategy_return'] = self.df['position'] * self.df['daily_return']
        self.df['cumulative_return'] = (1 + self.df['strategy_return']).cumprod() - 1
        self.df['pnl_percent'] = self.df['strategy_return'] * 100  # Daily PNL % for chart
        
        # Trade log
        trades = []
        position = 0
        entry_price = 0
        for i in range(1, len(self.df)):
            current_signal = int(self.df['signal'].iloc[i])
            prev_position = int(self.df['position'].iloc[i] or 0)
            
            if current_signal == 1 and prev_position != 1:  # Enter long
                if position == -1:  # Close short
                    exit_price = self.df['close'].iloc[i]
                    pnl_percent = ((entry_price - exit_price) / entry_price) * 100  # Short: sell high, buy low
                    trades.append({
                        'Date': self.df.index[i].strftime('%Y-%m-%d'),
                        'Action': 'Buy (Close Short)',
                        'Price': exit_price,
                        'PNL %': f"{pnl_percent:+.2f}"
                    })
                entry_price = self.df['close'].iloc[i]
                position = 1
                trades.append({
                    'Date': self.df.index[i].strftime('%Y-%m-%d'),
                    'Action': 'Buy',
                    'Price': entry_price,
                    'PNL %': 'N/A'
                })
            elif current_signal == -1 and prev_position != -1:  # Enter short
                if position == 1:  # Close long
                    exit_price = self.df['close'].iloc[i]
                    pnl_percent = ((exit_price - entry_price) / entry_price) * 100
                    trades.append({
                        'Date': self.df.index[i].strftime('%Y-%m-%d'),
                        'Action': 'Sell (Close Long)',
                        'Price': exit_price,
                        'PNL %': f"{pnl_percent:+.2f}"
                    })
                entry_price = self.df['close'].iloc[i]
                position = -1
                trades.append({
                    'Date': self.df.index[i].strftime('%Y-%m-%d'),
                    'Action': 'Sell',
                    'Price': entry_price,
                    'PNL %': 'N/A'
                })
            elif current_signal == 0 and prev_position != 0:  # Exit position
                exit_price = self.df['close'].iloc[i]
                if position == 1:  # Close long
                    pnl_percent = ((exit_price - entry_price) / entry_price) * 100
                    trades.append({
                        'Date': self.df.index[i].strftime('%Y-%m-%d'),
                        'Action': 'Sell',
                        'Price': exit_price,
                        'PNL %': f"{pnl_percent:+.2f}"
                    })
                elif position == -1:  # Close short
                    pnl_percent = ((entry_price - exit_price) / entry_price) * 100
                    trades.append({
                        'Date': self.df.index[i].strftime('%Y-%m-%d'),
                        'Action': 'Buy',
                        'Price': exit_price,
                        'PNL %': f"{pnl_percent:+.2f}"
                    })
                position = 0
        
        # Summary metrics
        total_return = self.df['cumulative_return'].iloc[-1] * 100
        daily_returns = self.df['strategy_return'].dropna()
        cumulative_max = self.df['cumulative_return'].cummax()
        drawdowns = (cumulative_max - self.df['cumulative_return']) / (1 + cumulative_max)
        max_drawdown = drawdowns.max() * 100
        sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252) if daily_returns.std() != 0 else 0
        
        self.backtest_results = {
            'pnl_df': self.df[['pnl_percent']].copy(),
            'trade_log': trades,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio
        }

    async def create_interactive_chart(self, is_backtest=False):
        """Create an interactive chart with PNL and trade log for backtest."""
        try:
            df = await self.fetch_historical_data()
            if df is None or df.empty:
                return {'error': f"No data available for {self.ticker}"}

            df = df[(df.index >= self.start_date) & (df.index <= self.end_date)]
            if df.empty:
                return {'error': f"No data within the specified range for {self.ticker}"}

            total_days = (self.end_date - self.start_date).days

            candlestick = go.Candlestick(
                x=df.index,
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='Price'
            )
            volume_colors = ['green' if (df['close'] > df['open']).iloc[i] else 'red' for i in range(len(df))]
            volume = go.Bar(x=df.index, y=df['volume'], name='Volume', marker_color=volume_colors, opacity=0.6)

            if is_backtest:
                if 'signal' not in df.columns:
                    return {'error': 'No strategy signals provided for backtest'}
                self.df = df
                self.calculate_pnl_and_trades()
                if not self.backtest_results:
                    return {'error': 'Backtest calculation failed'}

                pnl_trace = go.Bar(
                    x=self.backtest_results['pnl_df'].index,
                    y=self.backtest_results['pnl_df']['pnl_percent'],
                    name='PNL %',
                    marker_color=['green' if x > 0 else 'red' for x in self.backtest_results['pnl_df']['pnl_percent']]
                )
                trade_table = go.Table(
                    header=dict(values=['Date', 'Action', 'Price', 'PNL %'], fill_color='paleturquoise'),
                    cells=dict(values=[
                        [t['Date'] for t in self.backtest_results['trade_log']],
                        [t['Action'] for t in self.backtest_results['trade_log']],
                        [f"{t['Price']:.2f}" for t in self.backtest_results['trade_log']],
                        [t['PNL %'] for t in self.backtest_results['trade_log']]
                    ])
                )

                fig = make_subplots(
                    rows=2, cols=2,
                    specs=[[{"rowspan": 2}, {"type": "bar"}], [{"type": "table"}, None]],
                    column_widths=[0.7, 0.3],
                    row_heights=[0.7, 0.3],
                    vertical_spacing=0.05,
                    horizontal_spacing=0.05,
                    shared_xaxes=True
                )
                fig.add_trace(candlestick, row=1, col=1)
                fig.add_trace(volume, row=1, col=1, secondary_y=True)
                fig.add_trace(pnl_trace, row=1, col=2)
                fig.add_trace(trade_table, row=2, col=1)
                fig.update_layout(
                    title=f'{self.ticker} Backtest ({self.bar_size}, {total_days} days)',
                    template='plotly_white',
                    height=800,
                    showlegend=True,
                    yaxis_title='Price',
                    yaxis2_title='Volume',
                    yaxis3_title='PNL %',
                    xaxis2_title='Date'
                )
            else:
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
                fig.add_trace(candlestick, row=1, col=1)
                fig.add_trace(volume, row=2, col=1)
                fig.update_layout(
                    title=f'{self.ticker} Price and Volume ({self.bar_size}, {total_days} days)',
                    template='plotly_white',
                    height=800,
                    xaxis_rangeslider_visible=False,
                    showlegend=True,
                    yaxis1=dict(title='Price'),
                    yaxis2=dict(title='Volume'),
                    xaxis2=dict(title='Date')
                )

            chart_json = pio.to_json(fig)
            return json.loads(chart_json)

        except Exception as e:
            return {'error': f"Error generating chart: {str(e)}"}

# Routes
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
    """Render the backtest page with an initial chart."""
    ticker = "AAPL"
    start_date = "2024-01-01"
    end_date = "2024-12-31"
    bar_size = "1 day"
    visualizer = MarketDataVisualizer(ticker, start_date=start_date, end_date=end_date, bar_size=bar_size)
    # Simulate signals for initial load (replace with actual strategy in production)
    df = await visualizer.fetch_historical_data()
    df['signal'] = np.random.choice([1, -1, 0], size=len(df))  # Placeholder; replace with strategy logic
    visualizer.df = df
    chart_json = await visualizer.create_interactive_chart(is_backtest=True)
    if 'error' in chart_json:
        chart_html = f"<div style='color: red;'>{chart_json['error']}</div>"
        metrics = {'total_return': 0, 'max_drawdown': 0, 'sharpe_ratio': 0}
    else:
        chart_html = go.Figure(chart_json).to_html(full_html=False, include_plotlyjs='cdn', div_id="backtest-chart")
        metrics = {
            'total_return': visualizer.backtest_results['total_return'],
            'max_drawdown': visualizer.backtest_results['max_drawdown'],
            'sharpe_ratio': visualizer.backtest_results['sharpe_ratio']
        }
    return await render_template(
        'backtest.html',
        chart_html=chart_html,
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        lookback_multiplier='',
        bar_sizes=SUPPORTED_DURATIONS.keys(),
        selected_bar_size=bar_size,
        total_return=f"{metrics['total_return']:+.2f}",
        max_drawdown=f"-{metrics['max_drawdown']:.2f}",
        sharpe_ratio=f"{metrics['sharpe_ratio']:.2f}"
    )

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
            if not lookback_multiplier.isdigit():
                raise ValueError("Lookback multiplier must be a positive integer")
            lookback_multiplier = int(lookback_multiplier)
            if lookback_multiplier <= 0:
                raise ValueError("Lookback multiplier must be greater than 0")
            visualizer = MarketDataVisualizer(ticker, lookback_multiplier=lookback_multiplier, bar_size=bar_size)
        else:
            if not (start_date and end_date):
                raise ValueError("Please provide both start date and end date, or use a lookback multiplier")
            start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.datetime.strptime(end_date, "%Y-%m-%d")
            if end <= start:
                return jsonify({'error': 'End date must be after start date'}), 400
            visualizer = MarketDataVisualizer(ticker, start_date=start_date, end_date=end_date, bar_size=bar_size)

        if bar_size not in SUPPORTED_DURATIONS:
            return jsonify({'error': f"Invalid bar size: {bar_size}"}, SUPPORTED_DURATIONS), 400

        chart_json = await visualizer.create_interactive_chart()
        if 'error' in chart_json:
            return jsonify(chart_json), 400

        return jsonify(chart_json)
    
    except ValueError as e:
        return jsonify({'error': f"Invalid input: {str(e)}"}), 400
    except Exception as e:
        logger.error(f"Unexpected error in generate_chart: {str(e)}", exc_info=True)
        return jsonify({'error': f"Error: {str(e)}"}), 500

@app.route('/run_backtest', methods=['POST'])
async def run_backtest():
    """Handle backtest form submission."""
    form = await request.form
    ticker = form.get('ticker', 'AAPL').strip()
    start_date = form['start_date'].strip()
    end_date = form['end_date'].strip()
    bar_size = form.get('bar_size', '1 day').strip()
    strategy = form.get('strategy', '').strip()

    visualizer = MarketDataVisualizer(ticker, start_date=start_date, end_date=end_date, bar_size=bar_size)
    df = await visualizer.fetch_historical_data()
    # Placeholder: Replace with actual strategy logic based on 'strategy'
    df['signal'] = np.random.choice([1, -1, 0], size=len(df))  # Simulated signals
    visualizer.df = df
    chart_json = await visualizer.create_interactive_chart(is_backtest=True)
    if 'error' in chart_json:
        return jsonify({'error': chart_json['error']}), 400
    
    metrics = {
        'total_return': visualizer.backtest_results['total_return'],
        'max_drawdown': visualizer.backtest_results['max_drawdown'],
        'sharpe_ratio': visualizer.backtest_results['sharpe_ratio'],
        'chart_json': chart_json
    }
    return jsonify(metrics)

if __name__ == "__main__":
    app.run(debug=True)