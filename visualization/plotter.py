import plotly.graph_objects as go
from src.config import Config

class Plotter:
    def plot_ohlc(self, df, symbol, start_date, end_date, pnl):
        fig = go.Figure()
        
        # OHLC Candlestick
        fig.add_trace(go.Candlestick(
            x=df['date'],
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='OHLC'
        ))
        
        # Volume
        fig.add_trace(go.Bar(
            x=df['date'],
            y=df['volume'],
            name='Volume',
            yaxis='y2'
        ))
        
        fig.update_layout(
            title=f"Backtest {symbol} | {start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')} | PNL: ${pnl:.2f}",
            yaxis_title="$ Price",
            yaxis2=dict(title="Volume", overlaying='y', side='right'),
            xaxis_title="Date",
            template='plotly_dark'
        )
        
        fig.show()