# visualization/trading_dashboard.py
from ib_insync import IB, Stock, util
import pandas as pd
import plotly.graph_objects as go
import datetime
import os
from flask import Flask, render_template
import asyncio
from asgiref.wsgi import WsgiToAsgi  # Import WsgiToAsgi

app = Flask(__name__)

class MarketDataVisualizer:
    def __init__(self, ticker, days_back=30):
        self.ticker = ticker.upper()
        self.days_back = days_back
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
            contract = Stock(self.ticker, 'SMART', 'USD')
            end_date = datetime.datetime.now()
            start_date = end_date - datetime.timedelta(days=self.days_back)
            
            bars = await self.ib.reqHistoricalData(
                contract,
                endDateTime=end_date,
                durationStr=f'{self.days_back} D',
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
            await self.ib.disconnect()

    async def create_interactive_chart(self, output_html="templates/ib_trading_chart.html"):
        """Create an interactive candlestick chart with volume (green/red) in separate y-axes"""
        await self.fetch_historical_data()
        
        if self.df is None or self.df.empty:
            print("No data to plot")
            return

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

        # Layout with separate y-axes
        layout = go.Layout(
            title=f'{self.ticker} Price and Volume (IB TWS Data)',
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

        # Create figure and save as HTML
        fig = go.Figure(data=[candlestick, volume], layout=layout)
        fig.write_html(output_html)
        print(f"Chart saved as {output_html}")
        return output_html

@app.route('/')
async def show_chart():
    ticker = "AAPL"  # Default ticker, can be made dynamic via input or config
    days_back = 30
    visualizer = MarketDataVisualizer(ticker, days_back)
    chart_path = await visualizer.create_interactive_chart()
    return render_template('ib_trading_chart.html')

if __name__ == "__main__":
    # This block is optional for development, but we'll run with uvicorn instead
    pass

# Create an ASGI adapter for the Flask app
asgi_app = WsgiToAsgi(app)