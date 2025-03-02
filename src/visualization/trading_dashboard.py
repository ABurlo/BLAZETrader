import os
import datetime
import logging
import numpy as np
from quart import Quart, render_template, request, jsonify, session
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
app.secret_key = os.urandom(24)  # Secure random secret key

# Supported TWS API bar sizes and their maximum duration strings
SUPPORTED_DURATIONS = {
    '1 min': '1 min', '5 mins': '5 mins', '15 mins': '15 mins', '30 mins': '30 mins',
    '1 hour': '1 hour', '1 day': '1 day', '1 week': '1 week', '1 month': '1 month'
}
SUPPORTED_DURATION_STRINGS = {
    '1 min': '1 D', '5 mins': '5 D', '15 mins': '10 D', '30 mins': '20 D',
    '1 hour': '30 D', '1 day': '1 Y', '1 week': '2 Y', '1 month': '5 Y'
}
BAR_SIZE_MULTIPLIERS = {
    '1 min': 1, '5 mins': 5, '15 mins': 15, '30 mins': 30, '1 hour': 60,
    '1 day': 1440, '1 week': 10080, '1 month': 43200
}

class MarketDataVisualizer:
    def __init__(self, ticker, start_date=None, end_date=None, bar_size='1 day'):
        """Initialize the MarketDataVisualizer with ticker and date range."""
        self.ticker = ticker.upper()
        eastern = timezone('US/Eastern')
        self.end_date = eastern.localize(datetime.datetime.now()) if not end_date else eastern.localize(datetime.datetime.strptime(end_date, "%Y-%m-%d"))
        self.start_date = self.end_date - datetime.timedelta(days=365) if not start_date else eastern.localize(datetime.datetime.strptime(start_date, "%Y-%m-%d"))
        self.bar_size = bar_size
        self.ib = None
        self.df = None
        self.backtest_results = None

    async def connect_to_ib(self):
        """Establish connection to Interactive Brokers TWS."""
        self.ib = IB()
        try:
            await self.ib.connectAsync('127.0.0.1', 7497, clientId=10)
            logger.info("Connected to Interactive Brokers TWS")
        except Exception as e:
            logger.error(f"Connection error: {e}")
            self.ib = None
            raise ConnectionError(f"Failed to connect to IBKR: {e}")

    async def fetch_historical_data(self):
        """Fetch historical market data from Interactive Brokers."""
        try:
            if not self.ib or not self.ib.isConnected():
                await self.connect_to_ib()

            logger.info(f"Fetching data for {self.ticker} from {self.start_date} to {self.end_date} with bar size {self.bar_size}")
            contract = Stock(self.ticker, 'SMART', 'USD')
            duration_str = self._get_duration_string()
            bars = await self.ib.reqHistoricalDataAsync(
                contract, endDateTime=self.end_date, durationStr=duration_str,
                barSizeSetting=self.bar_size, whatToShow='TRADES', useRTH=True
            )
            if not bars:
                raise ValueError(f"No data received for {self.ticker}")

            self.df = self._process_historical_data(bars)
            logger.info(f"Data fetched successfully. Rows: {len(self.df)}, Columns: {self.df.columns.tolist()}")
            return self.df

        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            raise
        finally:
            if self.ib and self.ib.isConnected():
                logger.info("Disconnecting from IBKR")
                self.ib.disconnect()

    def _get_duration_string(self):
        """Calculate appropriate duration string based on bar size and date range."""
        days_diff = (self.end_date - self.start_date).days
        duration_str = SUPPORTED_DURATION_STRINGS.get(self.bar_size, '1 Y')
        duration_limits = {
            '1 min': 1, '5 mins': 5, '15 mins': 10, '30 mins': 20,
            '1 hour': 30, '1 day': 365, '1 week': 730, '1 month': 1825
        }
        if self.bar_size in duration_limits and days_diff > duration_limits[self.bar_size]:
            return f"{min(days_diff, duration_limits[self.bar_size])} D" if self.bar_size != '1 month' else f"{min(days_diff, 1825)} D"
        return duration_str

    def _process_historical_data(self, bars):
        """Process raw bar data into a cleaned DataFrame."""
        df = util.df(bars)
        required_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_columns):
            raise ValueError(f"Missing required columns: {df.columns.tolist()}")
        
        df.set_index('date', inplace=True)
        df.index = pd.to_datetime(df.index).tz_localize('US/Eastern', ambiguous='infer', nonexistent='shift_forward')
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        df.dropna(subset=['close', 'open', 'high', 'low', 'volume'], inplace=True)
        return df

    def generate_ema_signals(self):
        """Generate trading signals based on EMA crossovers."""
        if self.df is None or self.df.empty:
            logger.error("No data available for signal generation")
            return

        self.df['ema_9'] = self.df['close'].ewm(span=9, adjust=False).mean()
        self.df['ema_20'] = self.df['close'].ewm(span=20, adjust=False).mean()
        self.df['ema_200'] = self.df['close'].ewm(span=200, adjust=False).mean()
        self.df['signal'] = 0
        self.df['prev_ema_9'] = self.df['ema_9'].shift(1)
        self.df['prev_ema_20'] = self.df['ema_20'].shift(1)

        buy_condition = (self.df['ema_9'] > self.df['ema_20']) & (self.df['prev_ema_9'] <= self.df['prev_ema_20']) & (self.df['close'] > self.df['ema_200'])
        sell_condition = (self.df['ema_9'] < self.df['ema_20']) & (self.df['prev_ema_9'] >= self.df['prev_ema_20']) & (self.df['close'] < self.df['ema_200'])
        self.df.loc[buy_condition, 'signal'] = 1
        self.df.loc[sell_condition, 'signal'] = -1

    def calculate_pnl_and_trades(self, demo_balance=10000):
        """Calculate PNL and trade log based on signals."""
        if self.df is None or self.df.empty or 'signal' not in self.df.columns:
            logger.error("No data or signals available for PNL calculation")
            return

        self.df['signal'] = self.df['signal'].fillna(0).astype(float)
        self.df['position'] = self.df['signal'].shift(1).fillna(0).astype(float)
        self.df['balance'] = float(demo_balance)
        self.df['shares'] = 0.0
        self.df['value'] = 0.0

        trades = []
        position, shares, current_balance = 0, 0, float(demo_balance)

        for i in range(1, len(self.df)):
            current_signal = self.df['signal'].iloc[i]
            prev_position = self.df['position'].iloc[i]
            current_price = float(self.df['close'].iloc[i])

            if not np.isfinite(current_price):
                logger.warning(f"Skipping index {i} due to non-finite price: {current_price}")
                continue

            trades, position, shares, current_balance = self._process_trade(
                i, current_signal, prev_position, current_price, position, shares, current_balance, trades
            )
            self.df.loc[self.df.index[i], ['balance', 'shares', 'value']] = [
                float(current_balance) if np.isfinite(current_balance) else 0.0,
                float(shares),
                float(shares * current_price) if np.isfinite(shares * current_price) else 0.0
            ]

        self._finalize_backtest_results(demo_balance, trades)

    def _process_trade(self, i, current_signal, prev_position, current_price, position, shares, current_balance, trades):
        """Process individual trade logic."""
        if current_signal == 1 and prev_position != 1:
            if position == -1:
                trades, current_balance = self._close_short(i, current_price, shares, current_balance, trades)
            shares_to_buy = int(current_balance // current_price) if np.isfinite(current_balance / current_price) else 0
            if shares_to_buy > 0:
                current_balance -= shares_to_buy * current_price
                shares = shares_to_buy
                position = 1
                trades.append({'Date': self.df.index[i].strftime('%Y-%m-%d'), 'Action': 'Buy', 'Price': current_price, 'PNL %': 'N/A'})
        
        elif current_signal == -1 and prev_position != -1:
            if position == 1:
                trades, current_balance = self._close_long(i, current_price, shares, current_balance, trades)
            shares_to_short = int(current_balance // current_price) if np.isfinite(current_balance / current_price) else 0
            if shares_to_short > 0:
                shares = shares_to_short
                position = -1
                trades.append({'Date': self.df.index[i].strftime('%Y-%m-%d'), 'Action': 'Sell', 'Price': current_price, 'PNL %': 'N/A'})
        
        elif current_signal == 0 and prev_position != 0:
            if position == 1:
                trades, current_balance = self._close_long(i, current_price, shares, current_balance, trades)
            elif position == -1:
                trades, current_balance = self._close_short(i, current_price, shares, current_balance, trades)
            shares, position = 0, 0

        return trades, position, shares, current_balance

    def _close_short(self, i, current_price, shares, current_balance, trades):
        """Close a short position."""
        exit_price = current_price
        shares_sold = shares
        pnl = (exit_price - float(self.df['close'].iloc[i-1])) * shares_sold
        current_balance += pnl
        trades.append({
            'Date': self.df.index[i].strftime('%Y-%m-%d'), 'Action': 'Buy (Close Short)', 'Price': exit_price,
            'PNL %': f"{((pnl / (current_balance - pnl)) * 100):+.2f}" if np.isfinite(pnl) and (current_balance - pnl) != 0 else 'N/A'
        })
        return trades, current_balance

    def _close_long(self, i, current_price, shares, current_balance, trades):
        """Close a long position."""
        exit_price = current_price
        shares_sold = shares
        pnl = (float(self.df['close'].iloc[i-1]) - exit_price) * shares_sold
        current_balance += pnl
        trades.append({
            'Date': self.df.index[i].strftime('%Y-%m-%d'), 'Action': 'Sell (Close Long)', 'Price': exit_price,
            'PNL %': f"{((pnl / (current_balance - pnl)) * 100):+.2f}" if np.isfinite(pnl) and (current_balance - pnl) != 0 else 'N/A'
        })
        return trades, current_balance

    def _finalize_backtest_results(self, demo_balance, trades):
        """Calculate final backtest metrics including Sortino ratio."""
        self.df['pnl_percent'] = self.df['balance'].pct_change().replace([np.inf, -np.inf], np.nan) * 100
        daily_returns = self.df['balance'].pct_change().replace([np.inf, -np.inf], np.nan).dropna()
        total_return = ((self.df['balance'].iloc[-1] - demo_balance) / demo_balance) * 100 if np.isfinite(self.df['balance'].iloc[-1]) else 0.0
        cumulative_max = self.df['balance'].cummax()
        drawdowns = (cumulative_max - self.df['balance']) / (demo_balance + cumulative_max)
        max_drawdown = drawdowns.max() * 100 if not drawdowns.empty else 0.0
        sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252) if daily_returns.std() != 0 else 0.0
        downside_returns = daily_returns[daily_returns < 0]
        sortino_ratio = (daily_returns.mean() / downside_returns.std()) * np.sqrt(252) if downside_returns.std() != 0 else 0.0

        self.backtest_results = {
            'pnl_df': self.df[['pnl_percent', 'balance', 'shares', 'value']].copy().fillna(0.0),
            'trade_log': trades,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'final_balance': self.df['balance'].iloc[-1]
        }

    async def create_interactive_chart(self, demo_balance=10000):
        """Generate an interactive chart with backtest results."""
        try:
            df = await self.fetch_historical_data()
            if df is None or df.empty:
                return {'error': f"No data available for {self.ticker}"}

            df = df[(df.index >= self.start_date) & (df.index <= self.end_date)]
            if df.empty:
                return {'error': f"No data within the specified range for {self.ticker}"}

            total_days = (self.end_date - self.start_date).days
            self.df = df
            self.generate_ema_signals()
            self.calculate_pnl_and_trades(demo_balance)
            if not self.backtest_results:
                return {'error': 'Backtest calculation failed'}

            fig = self._create_plotly_figure(df, total_days)
            chart_json = pio.to_json(fig)
            return {
                'chart_json': json.loads(chart_json),
                'pnl_data': self._get_pnl_data(),
                'trade_log': self.backtest_results['trade_log'],
                'metrics': {
                    'total_return': self.backtest_results['total_return'],
                    'max_drawdown': self.backtest_results['max_drawdown'],
                    'sharpe_ratio': self.backtest_results['sharpe_ratio'],
                    'sortino_ratio': self.backtest_results['sortino_ratio'],
                    'final_balance': self.backtest_results['final_balance']
                }
            }

        except Exception as e:
            logger.error(f"Error in create_interactive_chart: {str(e)}")
            return {'error': f"Error generating chart: {str(e)}"}

    def _create_plotly_figure(self, df, total_days):
        """Create the Plotly figure with candlestick and volume subplots."""
        candle_colors = ['green' if row['close'] > row['open'] else 'red' for _, row in df.iterrows()]
        candlestick = go.Candlestick(
            x=df.index, open=df['open'].astype(float), high=df['high'].astype(float),
            low=df['low'].astype(float), close=df['close'].astype(float),
            increasing_line_color='green', decreasing_line_color='red',
            increasing_fillcolor='green', decreasing_fillcolor='red',
            line_width=1, name='Price'
        )
        volume_colors = ['green' if row['close'] > row['open'] else 'red' for _, row in df.iterrows()]
        volume = go.Bar(x=df.index, y=df['volume'].astype(float), name='Volume', marker_color=volume_colors, opacity=0.6, showlegend=True)

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.75, 0.25], specs=[[{"secondary_y": False}], [{"secondary_y": False}]])
        fig.add_trace(candlestick, row=1, col=1)
        fig.add_trace(volume, row=2, col=1)
        fig.update_layout(
            title=f'{self.ticker} Backtest ({self.bar_size}, {total_days} days)', template='plotly_dark', height=600, width=800,
            xaxis_rangeslider_visible=False, showlegend=True,
            yaxis1=dict(title='Price ($)', showgrid=True, gridcolor='rgba(255, 255, 255, 0.1)', zerolinecolor='rgba(255, 255, 255, 0.1)', tickformat='.2f'),
            yaxis2=dict(title='Volume', showgrid=True, gridcolor='rgba(255, 255, 255, 0.1)', zerolinecolor='rgba(255, 255, 255, 0.1)'),
            xaxis2=dict(title='Date', showgrid=True, gridcolor='rgba(255, 255, 255, 0.1)', type='date'),
            plot_bgcolor='rgba(0, 0, 0, 0)', paper_bgcolor='#2d2d2d', margin=dict(l=50, r=50, t=80, b=50)
        )
        return fig

    def _get_pnl_data(self):
        """Prepare PNL data for charting."""
        return {
            'x': self.backtest_results['pnl_df'].index.tolist(),
            'y': self.backtest_results['pnl_df']['pnl_percent'].fillna(0.0).tolist(),
            'type': 'bar', 'name': 'PNL %',
            'marker': {'color': ['green' if x > 0 else 'red' for x in self.backtest_results['pnl_df']['pnl_percent'].fillna(0.0)], 'opacity': 0.8}
        }

# Routes
@app.route('/')
async def index():
    return await render_template('home.html')

@app.route('/trading', methods=['GET', 'POST'])
async def trading():
    demo_balance = float(session.get('demo_balance', 10000))
    if request.method == 'POST':
        form = await request.form
        ticker = form.get('ticker', 'AAPL').strip()
        start_date = form.get('start_date', '2024-01-01').strip()
        end_date = form.get('end_date', '2024-12-31').strip()
        bar_size = form.get('bar_size', '1 day').strip()

        visualizer = MarketDataVisualizer(ticker, start_date=start_date, end_date=end_date, bar_size=bar_size)
        result = await visualizer.create_interactive_chart(demo_balance=demo_balance)
        if 'error' in result:
            chart_html = f"<div style='color: red; text-align: center;'>{result['error']}</div>"
            metrics = {
                'total_return': 0.0,
                'max_drawdown': 0.0,
                'sharpe_ratio': 0.0,
                'sortino_ratio': 0.0,
                'final_balance': demo_balance
            }
            pnl_data = trade_log = None
        else:
            chart_html = go.Figure(data=result['chart_json']['data'], layout=result['chart_json']['layout']).to_html(
                full_html=False, include_plotlyjs='cdn', div_id="trading-chart"
            )
            metrics = result['metrics']
            pnl_data = result.get('pnl_data')
            trade_log = result.get('trade_log')

        return await render_template(
            'trading.html', 
            chart_html=chart_html, 
            ticker=ticker, 
            start_date=start_date, 
            end_date=end_date,
            bar_sizes=SUPPORTED_DURATIONS.keys(), 
            selected_bar_size=bar_size,
            total_return=f"{metrics['total_return']:+.2f}", 
            max_drawdown=f"-{metrics['max_drawdown']:.2f}",
            sharpe_ratio=f"{metrics['sharpe_ratio']:.2f}", 
            sortino_ratio=f"{metrics['sortino_ratio']:.2f}",
            final_balance=metrics['final_balance'], 
            pnl_data=pnl_data, 
            trade_log=trade_log, 
            demo_balance=demo_balance
        )
    else:
        ticker, start_date, end_date, bar_size = "AAPL", "2024-01-01", "2024-12-31", "1 day"
        return await render_template(
            'trading.html', 
            chart_html='<div style="color: gray; text-align: center;">Run a backtest to see results.</div>',
            ticker=ticker, 
            start_date=start_date, 
            end_date=end_date, 
            bar_sizes=SUPPORTED_DURATIONS.keys(),
            selected_bar_size=bar_size, 
            total_return="0.00%", 
            max_drawdown="0.00%", 
            sharpe_ratio="0.00", 
            sortino_ratio="0.00",
            final_balance=demo_balance, 
            pnl_data=None, 
            trade_log=None, 
            demo_balance=demo_balance
        )

@app.route('/backtest', methods=['POST'])
async def run_backtest():
    form = await request.form
    ticker = form.get('ticker', 'AAPL').strip()
    start_date = form.get('start_date', '2024-01-01').strip()
    end_date = form.get('end_date', '2024-12-31').strip()
    bar_size = form.get('bar_size', '1 day').strip()
    demo_balance = float(form.get('demo_balance', session.get('demo_balance', 10000)))

    visualizer = MarketDataVisualizer(ticker, start_date=start_date, end_date=end_date, bar_size=bar_size)
    result = await visualizer.create_interactive_chart(demo_balance=demo_balance)
    if 'error' in result:
        return jsonify({'error': result['error']}), 400
    
    metrics = {
        'total_return': result['metrics']['total_return'],
        'max_drawdown': result['metrics']['max_drawdown'],
        'sharpe_ratio': result['metrics']['sharpe_ratio'],
        'sortino_ratio': result['metrics']['sortino_ratio'],
        'final_balance': result['metrics']['final_balance'],
        'chart_json': result['chart_json'],
        'pnl_data': result.get('pnl_data'),
        'trade_log': result.get('trade_log')
    }
    return jsonify(metrics)

@app.route('/set_demo_balance', methods=['POST'])
async def set_demo_balance():
    form = await request.form
    demo_balance = float(form.get('demo_balance', 10000))
    if demo_balance <= 0:
        return jsonify({'error': 'Demo balance must be positive'}), 400
    session['demo_balance'] = demo_balance
    return jsonify({'demo_balance': demo_balance, 'success': True})

@app.route('/strategies')
async def strategies():
    return await render_template('strategies.html')

@app.route('/portfolio', methods=['GET', 'POST'])
async def portfolio():
    if 'portfolio' not in session:
        session['portfolio'] = {}
        session['demo_balance'] = 100000.0  # Default demo balance

    portfolio = session['portfolio']
    demo_balance = session.get('demo_balance', 100000.0)

    if request.method == 'POST':
        form = await request.form
        action = form.get('action', 'buy')  # Default to 'buy' if not specified
        ticker = form.get('ticker', '').upper()
        shares = int(form.get('shares', 0)) if form.get('shares') and form.get('shares').strip() else 0

        logger.info(f"Processing action: {action} for ticker {ticker} with shares {shares}")

        if action in ('buy', 'sell', 'force-add') and ticker and shares > 0:
            # Fetch current price from IBKR using MarketDataVisualizer
            visualizer = MarketDataVisualizer(ticker)
            try:
                df = await visualizer.fetch_historical_data()
                current_price = df['close'].iloc[-1] if not df.empty else await fetch_current_price(ticker)
                if current_price <= 0:
                    return jsonify({'error': f'Failed to fetch current price for {ticker}', 'portfolio': portfolio, 'total_value': demo_balance + sum(data['value'] for data in portfolio.values() if 'value' in data), 'total_change': calculate_total_change(portfolio), 'demo_balance': demo_balance}), 500
            except Exception as e:
                logger.error(f"Error fetching price for {ticker}: {str(e)}")
                return jsonify({'error': f'Error fetching price for {ticker}: {str(e)}', 'portfolio': portfolio, 'total_value': demo_balance + sum(data['value'] for data in portfolio.values() if 'value' in data), 'total_change': calculate_total_change(portfolio), 'demo_balance': demo_balance}), 500

            trade_value = current_price * shares

            # Handle buy, sell, or force-add
            if action == 'buy':
                if ticker not in portfolio:
                    portfolio[ticker] = {
                        'shares': 0,
                        'price': current_price,
                        'value': 0,
                        'change': 0.0,
                        'initial_price': current_price  # Store initial price for change calculation
                    }
                if demo_balance >= trade_value:
                    portfolio[ticker]['shares'] += shares
                    portfolio[ticker]['value'] = portfolio[ticker]['shares'] * current_price
                    portfolio[ticker]['price'] = current_price
                    demo_balance -= trade_value
                else:
                    return jsonify({'error': 'Insufficient funds', 'portfolio': portfolio, 'total_value': demo_balance + sum(data['value'] for data in portfolio.values() if 'value' in data), 'total_change': calculate_total_change(portfolio), 'demo_balance': demo_balance}), 400

            elif action == 'sell':
                if ticker not in portfolio or portfolio[ticker]['shares'] < shares:
                    return jsonify({'error': f'You cannot sell {shares} shares of {ticker} - you only have {portfolio[ticker]["shares"] if ticker in portfolio else 0} shares', 'portfolio': portfolio, 'total_value': demo_balance + sum(data['value'] for data in portfolio.values() if 'value' in data), 'total_change': calculate_total_change(portfolio), 'demo_balance': demo_balance}), 400
                portfolio[ticker]['shares'] -= shares
                portfolio[ticker]['value'] = max(0, portfolio[ticker]['shares'] * current_price)  # Ensure value doesn’t go negative
                portfolio[ticker]['price'] = current_price
                demo_balance += trade_value

                # Remove ticker from portfolio if no shares remain
                if portfolio[ticker]['shares'] == 0:
                    del portfolio[ticker]

            elif action == 'force-add':
                current_price = float(form.get('current_price', 0))
                cost_basis = float(form.get('cost_basis', 0))
                if current_price <= 0 or cost_basis <= 0:
                    return jsonify({'error': 'Current price and cost basis must be positive', 'portfolio': portfolio, 'total_value': demo_balance + sum(data['value'] for data in portfolio.values() if 'value' in data), 'total_change': calculate_total_change(portfolio), 'demo_balance': demo_balance}), 400

                value = shares * current_price
                change = ((current_price - cost_basis) / cost_basis) * 100 if cost_basis != 0 else 0.0

                portfolio[ticker] = {
                    'shares': shares,
                    'price': current_price,
                    'value': value,
                    'change': change,
                    'initial_price': cost_basis  # Use cost basis as initial price for change calculation
                }

                # Optionally deduct value from demo balance (remove this if you don’t want it)
                demo_balance -= value
                session['demo_balance'] = max(demo_balance, 0)  # Ensure demo_balance doesn’t go negative

        session['portfolio'] = portfolio
        session['demo_balance'] = demo_balance
        session.modified = True  # Ensure session is marked as modified

        # Return updated portfolio data for AJAX updates, even on errors
        logger.info(f"Portfolio updated: {json.dumps({'portfolio': portfolio, 'demo_balance': demo_balance, 'total_value': demo_balance + sum(data['value'] for data in portfolio.values() if 'value' in data), 'total_change': calculate_total_change(portfolio)})}")
        return jsonify({
            'portfolio': portfolio,
            'total_value': demo_balance + sum(data['value'] for data in portfolio.values() if 'value' in data),
            'total_change': calculate_total_change(portfolio),
            'demo_balance': demo_balance
        })

    # For GET request, render the template with portfolio data
    total_value = demo_balance + sum(data['value'] for data in portfolio.values() if 'value' in data)
    total_change = calculate_total_change(portfolio)

    return await render_template(
        'portfolio.html',
        portfolio=portfolio,
        total_value=total_value,
        total_change=total_change,
        demo_balance=demo_balance
    )

@app.route('/settings', methods=['GET', 'POST'])
async def settings():
    if request.method == 'POST':
        form = await request.form
        demo_balance = float(form.get('demo_balance', session.get('demo_balance', 10000)))
        if demo_balance <= 0:
            return await render_template('settings.html', demo_balance=session.get('demo_balance', 10000), error="Demo balance must be positive")
        session['demo_balance'] = demo_balance
        return await render_template('settings.html', demo_balance=demo_balance, success="Demo balance updated successfully")
    return await render_template('settings.html', demo_balance=session.get('demo_balance', 10000))

@app.route('/logs')
async def logs():
    return await render_template('logs.html')

async def fetch_current_price(ticker):
    """Fetch the current price from IBKR using the latest daily close."""
    visualizer = MarketDataVisualizer(ticker)
    df = await visualizer.fetch_historical_data()
    return df['close'].iloc[-1] if not df.empty else 0.0

def calculate_total_change(portfolio):
    """Calculate the portfolio's total percentage change based on initial and current values."""
    if not portfolio:
        return 0.0
    total_initial_value = sum(data['initial_price'] * data['shares'] for data in portfolio.values() if 'initial_price' in data and 'shares' in data)
    total_current_value = sum(data['value'] for data in portfolio.values() if 'value' in data)
    if total_initial_value == 0:
        return 0.0
    return ((total_current_value - total_initial_value) / total_initial_value) * 100

if __name__ == "__main__":
    app.run(debug=True, host='172.20.10.3', port=8000)