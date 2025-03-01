from ib_insync import IB, Stock, util
import pandas as pd
import plotly.graph_objects as go
import datetime
import os
from quart import Quart, render_template, request, send_file

app = Quart(__name__)

class MarketDataVisualizer:
    def __init__(self, ticker, start_date, end_date):
        self.ticker = ticker.upper()
        self.start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        self.ib = None
        self.df = None

    async def connect_to_ib(self):
        """Connect to Interactive Brokers using ib_insync"""
        self.ib = IB()
        await self.ib.connectAsync('127.0.0.1', 7497, clientId=1)  # Use your TWS port
        print("Connected to Interactive Brokers TWS")

    async def fetch_historical_data(self):
        """Fetch historical market data from IB TWS"""
        try:
            if self.ib is None:
                await self.connect_to_ib()
            
            contract = Stock(self.ticker, 'SMART', 'USD')
            
            bars = await self.ib.reqHistoricalData(
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
            self.df.set_index('date', inplace=True)
            self.df.index = pd.to_datetime(self.df.index)
            return self.df
            
        except Exception as e:
            print(f"Error fetching data: {e}")
            return None
        finally:
            if self.ib:
                await self.ib.disconnect()

    async def create_interactive_chart(self, output_html="templates/ib_trading_chart.html"):
        """Create an interactive candlestick chart with volume (green/red) in separate y-axes"""
        await self.fetch_historical_data()
        
        if self.df is None or self.df.empty:
            print("No data to plot")
            return None

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

        # Ensure the templates directory exists
        os.makedirs(os.path.dirname(output_html), exist_ok=True)

        # Create figure and save as HTML
        fig = go.Figure(data=[candlestick, volume], layout=layout)
        fig.write_html(output_html)
        print(f"Chart saved as {output_html}")
        return output_html

@app.route('/')
async def index():
    """Render the initial HTML form"""
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
        chart_path = await visualizer.create_interactive_chart()
        if chart_path is None:
            return "Error generating chart", 500
        
        return await send_file(chart_path)
    
    except ValueError as e:
        return f"Invalid date format or ticker: {str(e)}", 400
    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)