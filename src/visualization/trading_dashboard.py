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

# Session configuration for demo balance
app.secret_key = os.urandom(24)

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
    def __init__(self, ticker, start_date=None, end_date=None, bar_size='1 day'):
        self.ticker = ticker.upper()
        eastern = timezone('US/Eastern')
        if start_date and end_date:
            self.start_date = eastern.localize(datetime.datetime.strptime(start_date, "%Y-%m-%d"))
            self.end_date = eastern.localize(datetime.datetime.strptime(end_date, "%Y-%m-%d"))
        else:
            self.end_date = eastern.localize(datetime.datetime.now())
            self.start_date = self.end_date - datetime.timedelta(days=365)
        self.bar_size = bar_size
        self.ib = None
        self.df = None
        self.backtest_results = None

    async def connect_to_ib(self):
        self.ib = IB()
        try:
            await self.ib.connectAsync('127.0.0.1', 7497, clientId=10)
            logger.info("Connected to Interactive Brokers TWS")
        except Exception as e:
            logger.error(f"Connection error: {e}")
            self.ib = None
            raise ConnectionError(f"Failed to connect to IBKR: {e}")

    async def fetch_historical_data(self):
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
            
            self.df.replace([np.inf, -np.inf], np.nan, inplace=True)
            self.df.dropna(subset=['close', 'open', 'high', 'low', 'volume'], inplace=True)
            return self.df
            
        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            raise
        finally:
            if self.ib and self.ib.isConnected():
                logger.info("Disconnecting from IBKR")
                self.ib.disconnect()

    def generate_ema_signals(self):
        if self.df is None or self.df.empty:
            logger.error("No data available for signal generation")
            return

        self.df['ema_9'] = self.df['close'].ewm(span=9, adjust=False).mean()
        self.df['ema_20'] = self.df['close'].ewm(span=20, adjust=False).mean()
        self.df['ema_200'] = self.df['close'].ewm(span=200, adjust=False).mean()

        self.df['signal'] = 0
        self.df['prev_ema_9'] = self.df['ema_9'].shift(1)
        self.df['prev_ema_20'] = self.df['ema_20'].shift(1)

        buy_condition = (self.df['ema_9'] > self.df['ema_20']) & \
                        (self.df['prev_ema_9'] <= self.df['prev_ema_20']) & \
                        (self.df['close'] > self.df['ema_200'])
        self.df.loc[buy_condition, 'signal'] = 1

        sell_condition = (self.df['ema_9'] < self.df['ema_20']) & \
                         (self.df['prev_ema_9'] >= self.df['prev_ema_20']) & \
                         (self.df['close'] < self.df['ema_200'])
        self.df.loc[sell_condition, 'signal'] = -1

    def calculate_pnl_and_trades(self, demo_balance=10000):
        if self.df is None or self.df.empty or 'signal' not in self.df.columns:
            logger.error("No data or signals available for PNL calculation")
            return
        
        self.df['signal'] = self.df['signal'].fillna(0).astype(float)
        self.df['position'] = self.df['signal'].shift(1).fillna(0).astype(float)
        
        self.df['balance'] = float(demo_balance)
        self.df['shares'] = 0.0
        self.df['value'] = 0.0

        trades = []
        position = 0
        shares = 0
        current_balance = float(demo_balance)

        for i in range(1, len(self.df)):
            current_signal = self.df['signal'].iloc[i]
            prev_position = self.df['position'].iloc[i]
            current_price = float(self.df['close'].iloc[i])

            if not np.isfinite(current_price):
                logger.warning(f"Skipping index {i} due to non-finite price: {current_price}")
                continue
            
            if current_signal == 1 and prev_position != 1:
                if position == -1:
                    exit_price = current_price
                    shares_sold = shares
                    pnl = (exit_price - float(self.df['close'].iloc[i-1])) * shares_sold
                    current_balance += pnl
                    trades.append({
                        'Date': self.df.index[i].strftime('%Y-%m-%d'),
                        'Action': 'Buy (Close Short)',
                        'Price': exit_price,
                        'PNL %': f"{((pnl / (current_balance - pnl)) * 100):+.2f}" if np.isfinite(pnl) and (current_balance - pnl) != 0 else 'N/A'
                    })
                    shares = 0
                shares_to_buy = int(current_balance // current_price) if np.isfinite(current_balance / current_price) else 0
                if shares_to_buy > 0:
                    current_balance -= shares_to_buy * current_price
                    shares = shares_to_buy
                    position = 1
                    trades.append({
                        'Date': self.df.index[i].strftime('%Y-%m-%d'),
                        'Action': 'Buy',
                        'Price': current_price,
                        'PNL %': 'N/A'
                    })
            
            elif current_signal == -1 and prev_position != -1:
                if position == 1:
                    exit_price = current_price
                    shares_sold = shares
                    pnl = (float(self.df['close'].iloc[i-1]) - exit_price) * shares_sold
                    current_balance += pnl
                    trades.append({
                        'Date': self.df.index[i].strftime('%Y-%m-%d'),
                        'Action': 'Sell (Close Long)',
                        'Price': exit_price,
                        'PNL %': f"{((pnl / (current_balance - pnl)) * 100):+.2f}" if np.isfinite(pnl) and (current_balance - pnl) != 0 else 'N/A'
                    })
                    shares = 0
                shares_to_short = int(current_balance // current_price) if np.isfinite(current_balance / current_price) else 0
                if shares_to_short > 0:
                    shares = shares_to_short
                    position = -1
                    trades.append({
                        'Date': self.df.index[i].strftime('%Y-%m-%d'),
                        'Action': 'Sell',
                        'Price': current_price,
                        'PNL %': 'N/A'
                    })
            
            elif current_signal == 0 and prev_position != 0:
                exit_price = current_price
                if position == 1:
                    pnl = (exit_price - float(self.df['close'].iloc[i-1])) * shares
                    current_balance += pnl
                    trades.append({
                        'Date': self.df.index[i].strftime('%Y-%m-%d'),
                        'Action': 'Sell',
                        'Price': exit_price,
                        'PNL %': f"{((pnl / (current_balance - pnl)) * 100):+.2f}" if np.isfinite(pnl) and (current_balance - pnl) != 0 else 'N/A'
                    })
                elif position == -1:
                    pnl = (float(self.df['close'].iloc[i-1]) - exit_price) * shares
                    current_balance += pnl
                    trades.append({
                        'Date': self.df.index[i].strftime('%Y-%m-%d'),
                        'Action': 'Buy',
                        'Price': exit_price,
                        'PNL %': f"{((pnl / (current_balance - pnl)) * 100):+.2f}" if np.isfinite(pnl) and (current_balance - pnl) != 0 else 'N/A'
                    })
                shares = 0
                position = 0
            
            self.df.loc[self.df.index[i], 'balance'] = float(current_balance) if np.isfinite(current_balance) else 0.0
            self.df.loc[self.df.index[i], 'shares'] = float(shares)
            self.df.loc[self.df.index[i], 'value'] = float(shares * current_price) if np.isfinite(shares * current_price) else 0.0

        total_return = ((current_balance - demo_balance) / demo_balance) * 100 if np.isfinite(current_balance) else 0.0
        daily_returns = self.df['balance'].pct_change().replace([np.inf, -np.inf], np.nan).dropna()
        cumulative_max = self.df['balance'].cummax()
        drawdowns = (cumulative_max - self.df['balance']) / (demo_balance + cumulative_max)
        drawdowns.replace([np.inf, -np.inf], np.nan, inplace=True)
        max_drawdown = drawdowns.max() * 100 if not drawdowns.empty else 0.0
        sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252) if daily_returns.std() != 0 else 0.0
        
        self.df['pnl_percent'] = self.df['balance'].pct_change().replace([np.inf, -np.inf], np.nan) * 100

        self.backtest_results = {
            'pnl_df': self.df[['pnl_percent', 'balance', 'shares', 'value']].copy().fillna(0.0),
            'trade_log': trades,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'final_balance': current_balance
        }

    async def create_interactive_chart(self, demo_balance=10000):
        try:
            df = await self.fetch_historical_data()
            if df is None or df.empty:
                return {'error': f"No data available for {self.ticker}"}

            df = df[(df.index >= self.start_date) & (df.index <= self.end_date)]
            if df.empty:
                return {'error': f"No data within the specified range for {self.ticker}"}

            total_days = (self.end_date - self.start_date).days

            # Create Doji candlestick trace with green/red coloring
            candle_colors = ['green' if row['close'] > row['open'] else 'red' for _, row in df.iterrows()]
            candlestick = go.Candlestick(
                x=df.index,
                open=df['open'].astype(float),
                high=df['high'].astype(float),
                low=df['low'].astype(float),
                close=df['close'].astype(float),
                increasing_line_color='green',  # Green for up days
                decreasing_line_color='red',    # Red for down days
                increasing_fillcolor='green',
                decreasing_fillcolor='red',
                line_width=1,  # Thin lines for Doji style
                name='Price'
            )

            # Create vertical volume bars with green/red coloring
            volume_colors = ['green' if row['close'] > row['open'] else 'red' for _, row in df.iterrows()]
            volume = go.Bar(
                x=df.index,
                y=df['volume'].astype(float),
                name='Volume',
                marker_color=volume_colors,
                opacity=0.6,
                showlegend=True
            )

            # Perform backtest
            self.df = df
            self.generate_ema_signals()
            self.calculate_pnl_and_trades(demo_balance=demo_balance)
            if not self.backtest_results:
                return {'error': 'Backtest calculation failed'}

            # Create subplots with reduced height for volume
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.05,  # Reduced spacing for compactness
                row_heights=[0.75, 0.25],  # 75% for price, 25% for volume (less tall)
                specs=[[{"secondary_y": False}], [{"secondary_y": False}]]
            )
            fig.add_trace(candlestick, row=1, col=1)
            fig.add_trace(volume, row=2, col=1)
            fig.update_layout(
                title=f'{self.ticker} Backtest ({self.bar_size}, {total_days} days)',
                template='plotly_dark',
                height=600,
                width=800,
                xaxis_rangeslider_visible=False,
                showlegend=True,
                yaxis1=dict(
                    title='Price ($)',  # Price in dollars
                    showgrid=True,
                    gridcolor='rgba(255, 255, 255, 0.1)',  # Light gray grid for dark theme
                    zerolinecolor='rgba(255, 255, 255, 0.1)',
                    tickformat='.2f'  # Format price to 2 decimal places
                ),
                yaxis2=dict(
                    title='Volume',
                    showgrid=True,
                    gridcolor='rgba(255, 255, 255, 0.1)',  # Light gray grid for dark theme
                    zerolinecolor='rgba(255, 255, 255, 0.1)'
                ),
                xaxis2=dict(
                    title='Date',  # Time based on user timeframe
                    showgrid=True,
                    gridcolor='rgba(255, 255, 255, 0.1)',
                    type='date'  # Ensure date formatting
                ),
                plot_bgcolor='rgba(0, 0, 0, 0)',  # Transparent plot background
                paper_bgcolor='#2d2d2d',  # Match card background
                margin=dict(l=50, r=50, t=80, b=50)  # Adjust margins for better fit
            )

            # Prepare PNL data for a separate chart
            pnl_data = {
                'x': self.backtest_results['pnl_df'].index.tolist(),
                'y': self.backtest_results['pnl_df']['pnl_percent'].fillna(0.0).tolist(),
                'type': 'bar',
                'name': 'PNL %',
                'marker': {
                    'color': ['green' if x > 0 else 'red' for x in self.backtest_results['pnl_df']['pnl_percent'].fillna(0.0)],
                    'opacity': 0.8
                }
            }

            # Trade log remains a list of dictionaries
            trade_log = self.backtest_results['trade_log']

            chart_json = pio.to_json(fig)
            return {
                'chart_json': json.loads(chart_json),
                'pnl_data': pnl_data,
                'trade_log': trade_log,
                'metrics': {
                    'total_return': self.backtest_results['total_return'],
                    'max_drawdown': self.backtest_results['max_drawdown'],
                    'sharpe_ratio': self.backtest_results['sharpe_ratio'],
                    'final_balance': self.backtest_results['final_balance']
                }
            }

        except Exception as e:
            logger.error(f"Error in create_interactive_chart: {str(e)}")
            return {'error': f"Error generating chart: {str(e)}"}

# Routes
@app.route('/')
async def index():
    return await render_template('home.html')

@app.route('/trading', methods=['GET', 'POST'])
async def trading():
    if request.method == 'POST':
        form = await request.form
        ticker = form.get('ticker', 'AAPL').strip()
        start_date = form.get('start_date', '2024-01-01').strip()
        end_date = form.get('end_date', '2024-12-31').strip()
        bar_size = form.get('bar_size', '1 day').strip()
        demo_balance = float(session.get('demo_balance', 10000))

        visualizer = MarketDataVisualizer(ticker, start_date=start_date, end_date=end_date, bar_size=bar_size)
        chart_json = await visualizer.create_interactive_chart(demo_balance=demo_balance)
        if 'error' in chart_json:
            chart_html = f"<div style='color: red; text-align: center;'>{chart_json['error']}</div>"
            metrics = {'total_return': 0, 'max_drawdown': 0, 'sharpe_ratio': 0, 'final_balance': demo_balance}
            pnl_data = None
            trade_log = None
        else:
            fig = go.Figure(data=chart_json['chart_json']['data'], layout=chart_json['chart_json']['layout'])
            chart_html = fig.to_html(full_html=False, include_plotlyjs='cdn', div_id="trading-chart")
            metrics = chart_json['metrics']
            pnl_data = chart_json.get('pnl_data')
            trade_log = chart_json.get('trade_log')

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
            final_balance=metrics['final_balance'],
            pnl_data=pnl_data,
            trade_log=trade_log,
            demo_balance=demo_balance
        )
    else:
        ticker = "AAPL"
        start_date = "2024-01-01"
        end_date = "2024-12-31"
        bar_size = "1 day"
        demo_balance = float(session.get('demo_balance', 10000))

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
    chart_json = await visualizer.create_interactive_chart(demo_balance=demo_balance)
    if 'error' in chart_json:
        return jsonify({'error': chart_json['error']}), 400
    
    metrics = {
        'total_return': chart_json['metrics']['total_return'],
        'max_drawdown': chart_json['metrics']['max_drawdown'],
        'sharpe_ratio': chart_json['metrics']['sharpe_ratio'],
        'final_balance': chart_json['metrics']['final_balance'],
        'chart_json': chart_json['chart_json'],
        'pnl_data': chart_json.get('pnl_data'),
        'trade_log': chart_json.get('trade_log')
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
        session['portfolio'] = {
            'AAPL': {'shares': 100, 'price': 175.30, 'value': 17530.00, 'change': 1.2},
            'TSLA': {'shares': 50, 'price': 210.45, 'value': 10522.50, 'change': -0.8}
        }
    
    if request.method == 'POST':
        form = await request.form
        action = form.get('action')
        ticker = form.get('ticker')
        shares = int(form.get('shares', 0))
        
        if action == 'buy' and ticker and shares > 0:
            visualizer = MarketDataVisualizer(ticker)
            df = await visualizer.fetch_historical_data()
            current_price = df['close'].iloc[-1] if not df.empty else 0
            if current_price > 0:
                current_balance = session.get('demo_balance', 10000)
                cost = current_price * shares
                if cost <= current_balance:
                    if ticker in session['portfolio']:
                        session['portfolio'][ticker]['shares'] += shares
                        session['portfolio'][ticker]['value'] += cost
                    else:
                        session['portfolio'][ticker] = {'shares': shares, 'price': current_price, 'value': cost, 'change': 0}
                    session['demo_balance'] = current_balance - cost
                    session['portfolio'][ticker]['price'] = current_price
                    session['portfolio'][ticker]['change'] = np.random.uniform(-2, 2)
        elif action == 'sell' and ticker and shares > 0:
            if ticker in session['portfolio']:
                if session['portfolio'][ticker]['shares'] >= shares:
                    visualizer = MarketDataVisualizer(ticker)
                    df = await visualizer.fetch_historical_data()
                    current_price = df['close'].iloc[-1] if not df.empty else 0
                    if current_price > 0:
                        revenue = current_price * shares
                        session['portfolio'][ticker]['shares'] -= shares
                        session['portfolio'][ticker]['value'] -= revenue
                        session['portfolio'][ticker]['price'] = current_price
                        session['portfolio'][ticker]['change'] = np.random.uniform(-2, 2)
                        current_balance = session.get('demo_balance', 10000)
                        session['demo_balance'] = current_balance + revenue
                        if session['portfolio'][ticker]['shares'] == 0:
                            del session['portfolio'][ticker]

        total_value = sum(item['value'] for item in session['portfolio'].values())
        total_change = sum(item['change'] for item in session['portfolio'].values()) / len(session['portfolio']) if session['portfolio'] else 0

    else:
        total_value = sum(item['value'] for item in session['portfolio'].values())
        total_change = sum(item['change'] for item in session['portfolio'].values()) / len(session['portfolio']) if session['portfolio'] else 0

    return await render_template(
        'portfolio.html',
        portfolio=session['portfolio'],
        total_value=f"${total_value:.2f}",
        total_change=f"{total_change:+.2f}%",
        demo_balance=session.get('demo_balance', 10000)
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

    demo_balance = session.get('demo_balance', 10000)
    return await render_template('settings.html', demo_balance=demo_balance)

@app.route('/logs')
async def logs():
    return await render_template('logs.html')

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8000)