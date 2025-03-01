# src/visualization/trading_dashboard.py

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime
import webbrowser
import numpy as np
from data.data_manager import DataManager  # Import DataManager

class TradingDashboard:
    def __init__(self):
        """Initialize the TradingDashboard with an empty 2x2 grid configuration and DataManager."""
        self.fig = None
        self.slots = {
            'TL': (1, 1),  # Top-Left (Slot 1)
            'TR': (1, 2),  # Top-Right (Slot 2)
            'BR': (2, 2),  # Bottom-Right (Slot 3)
            'BL': (2, 1)   # Bottom-Left (Slot 4)
        }
        self.pane_configs = {}  # Store pane configurations (type, data, etc.)
        self.data_manager = DataManager()  # Initialize DataManager

    async def connect_to_ibkr(self):
        """Asynchronously connect to IBKR using DataManager."""
        await self.data_manager.connect()

    def add_pane(self, slot, pane_type, df=None, symbol=None, start_date=None, end_date=None, title=None, **kwargs):
        """
        Add a pane (e.g., OHLC, Volume, Placeholder) to a specific slot in the 2x2 grid.
        If no DataFrame is provided, fetch data from IBKR using DataManager.
        
        Args:
            slot (str): Slot position ('TL', 'TR', 'BR', 'BL')
            pane_type (str): Type of pane ('ohlc', 'volume', 'placeholder', 'top_gapper', 'fifty_two_week_lows')
            df (pd.DataFrame, optional): DataFrame with columns 'date', 'open', 'high', 'low', 'close', 'volume'
            symbol (str, optional): Ticker symbol for IBKR data fetch (required if df is None)
            start_date (str or datetime, optional): Start date in 'DD/MM/YYYY' format or datetime object (required if df is None)
            end_date (str or datetime, optional): End date in 'DD/MM/YYYY' format or datetime object (required if df is None)
            title (str, optional): Custom title for the pane
            **kwargs: Additional parameters for customization (e.g., colors, scales)
        """
        if slot not in self.slots:
            raise ValueError(f"Invalid slot: {slot}. Use 'TL', 'TR', 'BR', or 'BL'.")
        
        # Fetch data from IBKR if no DataFrame is provided
        if df is None and (symbol and start_date and end_date):
            if not self.data_manager.ib.isConnected():
                raise ConnectionError("Not connected to IBKR. Call connect_to_ibkr() first.")
            # Convert dates to datetime for IBKR
            if isinstance(start_date, str):
                start_dt = datetime.strptime(start_date, '%d/%m/%Y')
            else:
                start_dt = start_date
            if isinstance(end_date, str):
                end_dt = datetime.strptime(end_date, '%d/%m/%Y')
            else:
                end_dt = end_date
            df = self.data_manager.fetch_historical_data(symbol, start_dt, end_dt, timeframe="1 day")
        elif df is None:
            raise ValueError("Either provide a DataFrame or symbol, start_date, and end_date.")

        row, col = self.slots[slot]
        self.pane_configs[slot] = {
            'type': pane_type,
            'df': df,
            'title': title or f"Slot {slot[0]} ({slot})",
            'kwargs': kwargs
        }

    def _create_ohlc_pane(self, df, **kwargs):
        """Create an OHLC candlestick chart for price action."""
        dates = df['date'].dt.to_pydatetime()
        return go.Candlestick(
            x=dates,
            open=df['open'].values,
            high=df['high'].values,
            low=df['low'].values,
            close=df['close'].values,
            name='OHLC',
            increasing_line_color='green',
            decreasing_line_color='red',
            **kwargs
        )

    def _create_volume_pane(self, df, **kwargs):
        """Create a volume bar chart combining buy and sell volumes."""
        dates = df['date'].dt.to_pydatetime()
        buy_volumes = []
        sell_volumes = []
        for open_price, close_price, volume in zip(df['open'].values, df['close'].values, df['volume'].values):
            if close_price > open_price:  # Upward candle = buy volume
                buy_volumes.append(volume)
                sell_volumes.append(0)
            elif close_price < open_price:  # Downward candle = sell volume
                buy_volumes.append(0)
                sell_volumes.append(volume)
            else:  # No change, split evenly
                buy_volumes.append(volume / 2)
                sell_volumes.append(volume / 2)

        total_volumes = [buy + sell for buy, sell in zip(buy_volumes, sell_volumes)]
        buy_colors = ['green' if buy > 0 else 'red' for buy in buy_volumes]  # Green for buy, red for sell
        return go.Bar(
            x=dates,
            y=total_volumes,
            name='Volume',
            marker_color=buy_colors,
            **kwargs
        )

    def _create_placeholder_pane(self, **kwargs):
        """Create a placeholder chart (horizontal line at y=0)."""
        return go.Scatter(
            x=[0, 1],
            y=[0, 0],
            mode='lines',
            name='Placeholder',
            line_color='gray',
            **kwargs
        )

    def _create_top_gapper_pane(self, df, **kwargs):
        """Placeholder for future top gapper pane (e.g., top performing stocks by gap)."""
        # This is a placeholder method; implement based on your IBKR data structure later
        dates = df['date'].dt.to_pydatetime()
        return go.Scatter(
            x=dates,
            y=np.random.uniform(0, 1, len(dates)),  # Dummy data for now
            mode='lines',
            name='Top Gapper',
            line_color='blue',
            **kwargs
        )

    def _create_fifty_two_week_lows_pane(self, df, **kwargs):
        """Placeholder for future 52-week lows pane (e.g., stocks at 52-week lows)."""
        # This is a placeholder method; implement based on your IBKR data structure later
        dates = df['date'].dt.to_pydatetime()
        return go.Scatter(
            x=dates,
            y=np.random.uniform(0, 1, len(dates)),  # Dummy data for now
            mode='lines',
            name='52-Week Lows',
            line_color='purple',
            **kwargs
        )

    async def build_dashboard(self, start_date, end_date, pnl, symbol=None):
        """
        Asynchronously build and render the 2x2 dashboard with the configured panes.
        
        Args:
            start_date (str or datetime): Start date in 'DD/MM/YYYY' format or datetime object.
            end_date (str or datetime): End date in 'DD/MM/YYYY' format or datetime object.
            pnl (float): Profit and Loss value for the chart title.
            symbol (str, optional): Ticker symbol for the chart title (defaults to None if not provided)
        """
        # Handle date formatting
        if isinstance(start_date, str):
            start_dt = datetime.strptime(start_date, '%d/%m/%Y')
        else:
            start_dt = start_date

        if isinstance(end_date, str):
            end_dt = datetime.strptime(end_date, '%d/%m/%Y')
        else:
            end_dt = end_date

        symbol = symbol or 'AMZN'  # Default symbol if not provided

        # Create 2x2 subplot grid with explicit domains for independence
        self.fig = make_subplots(
            rows=2, cols=2,
            specs=[[{'type': 'xy'}, {'type': 'xy'}],
                   [{'type': 'xy'}, {'type': 'xy'}]],
            subplot_titles=[config['title'] for config in self.pane_configs.values()],
            row_heights=[0.5, 0.5],  # Equal height for rows
            vertical_spacing=0.05,  # Minimize vertical spacing
            horizontal_spacing=0.05,  # Minimize horizontal spacing
            column_widths=[0.5, 0.5]  # Equal width for columns
        )

        # Add panes to their respective slots
        for slot, config in self.pane_configs.items():
            row, col = self.slots[slot]
            df = config['df']
            pane_type = config['type']
            kwargs = config['kwargs']

            if pane_type == 'ohlc':
                trace = self._create_ohlc_pane(df, **kwargs)
            elif pane_type == 'volume':
                trace = self._create_volume_pane(df, **kwargs)
            elif pane_type == 'placeholder':
                trace = self._create_placeholder_pane(**kwargs)
            elif pane_type == 'top_gapper':
                trace = self._create_top_gapper_pane(df, **kwargs)
            elif pane_type == 'fifty_two_week_lows':
                trace = self._create_fifty_two_week_lows_pane(df, **kwargs)
            else:
                raise ValueError(f"Unknown pane type: {pane_type}")

            self.fig.add_trace(trace, row=row, col=col)

        # Update layout for dark gray mode with dynamic sizing (1/4 of screen)
        dark_gray = 'rgba(30,30,30,1)'  # Dark gray background (RGB: 30,30,30)
        light_gray = 'rgba(50,50,50,1)'  # Slightly lighter gray for contrast
        text_color = 'rgba(200,200,200,1)'  # Light gray text for contrast

        self.fig.update_layout(
            title=f'Dashboard with Backtest {symbol.upper()} | {start_dt.strftime("%d/%m/%Y")} - {end_dt.strftime("%d/%m/%Y")} | P&L: ${pnl:.2f}',
            paper_bgcolor=dark_gray,  # Dark gray background
            plot_bgcolor=light_gray,  # Slightly lighter gray for plot area
            font_color=text_color,  # Light gray text for contrast
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor=dark_gray, font_color=text_color),
            height=800,  # Set a reasonable height to allow scrolling if content exceeds screen size
            xaxis_rangeslider_visible=True,  # Add range slider for Slot 1 (if OHLC is there)
            grid=dict(rows=2, columns=2),  # Ensure grid structure is explicit
        )

        # Update axes for dark gray mode, ensure placeholders start at y=0
        for i in range(1, 3):
            for j in range(1, 3):
                self.fig.update_xaxes(
                    gridcolor='rgba(70,70,70,1)', 
                    zerolinecolor='rgba(70,70,70,1)', 
                    showgrid=True, 
                    color=text_color, 
                    row=i, 
                    col=j
                )
                self.fig.update_yaxes(
                    gridcolor='rgba(70,70,70,1)', 
                    zerolinecolor='rgba(70,70,70,1)', 
                    showgrid=True, 
                    color=text_color, 
                    range=[0, None] if i == 2 and j in [1, 2] else None,  # Force y-axis to start at 0 for row 2 (Slots 3 and 4)
                    row=i, 
                    col=j
                )

        # Specific axes updates for each slot
        for slot, (row, col) in self.slots.items():
            if slot in self.pane_configs:
                pane_type = self.pane_configs[slot]['type']
                if pane_type == 'ohlc':
                    self.fig.update_xaxes(
                        title='Time',
                        domain=[0.0, 0.45] if col == 1 else [0.55, 1.0],  # Left slots (TL, BL) or Right slots (TR, BR)
                        gridcolor='rgba(70,70,70,1)', 
                        zerolinecolor='rgba(70,70,70,1)', 
                        showgrid=True, 
                        color=text_color, 
                        rangeslider_visible=True if slot == 'TL' else False,  # Range slider only for Slot 1 (TL)
                        row=row, col=col
                    )
                    self.fig.update_yaxes(
                        title='Price ($)' if pane_type == 'ohlc' else None,
                        domain=[0.55, 1.0] if row == 1 else [0.0, 0.45],  # Top row (TL, TR) or Bottom row (BL, BR)
                        gridcolor='rgba(70,70,70,1)', 
                        zerolinecolor='rgba(70,70,70,1)', 
                        showgrid=True, 
                        color=text_color, 
                        row=row, col=col
                    )
                elif pane_type == 'volume':
                    self.fig.update_yaxes(
                        title='Volume',
                        domain=[0.0, 0.45],  # Bottom half for volume (only in Slot 1-B, e.g., BL)
                        gridcolor='rgba(70,70,70,1)', 
                        zerolinecolor='rgba(70,70,70,1)', 
                        showgrid=True, 
                        color=text_color, 
                        range=[0, None],  # Ensure volume starts at 0
                        row=row, col=col, secondary_y=True  # Secondary y-axis for volume
                    )
                elif pane_type in ['placeholder', 'top_gapper', 'fifty_two_week_lows']:
                    self.fig.update_yaxes(
                        domain=[0.55, 1.0] if row == 1 else [0.0, 0.45],  # Top or bottom row
                        gridcolor='rgba(70,70,70,1)', 
                        zerolinecolor='rgba(70,70,70,1)', 
                        showgrid=True, 
                        color=text_color, 
                        range=[0, None],  # Start at y=0 for placeholders
                        row=row, col=col
                    )

        # Save and open the dashboard in a browser
        html_content = self.fig.to_html(include_plotlyjs='cdn', full_html=True)
        with open(f"dashboard_{symbol}_{start_dt.strftime('%d_%m_%Y')}_{end_dt.strftime('%d_%m_%Y')}.html", "w") as f:
            f.write(html_content)
        webbrowser.open(f"dashboard_{symbol}_{start_dt.strftime('%d_%m_%Y')}_{end_dt.strftime('%d_%m_%Y')}.html", new=2)  # new=2 opens in a new tab

    def clear_panes(self):
        """Clear all pane configurations."""
        self.pane_configs.clear()

    def disconnect_from_ibkr(self):
        """Disconnect from IBKR using DataManager."""
        self.data_manager.disconnect()