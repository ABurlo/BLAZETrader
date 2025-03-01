import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime
import webbrowser
import numpy as np

class MultiPlotter:
    def create_dashboard(self, df, symbol, start_date, end_date, pnl):
        """
        Create a dashboard with four slots (2x2 grid) for financial data visualization.
        
        Args:
            df (pd.DataFrame): DataFrame with columns 'date', 'open', 'high', 'low', 'close', 'volume'
            symbol (str): The ticker symbol for the chart title.
            start_date (str or datetime): Start date in 'YYYY-MM-DD' format or datetime object.
            end_date (str or datetime): End date in 'YYYY-MM-DD' format or datetime object.
            pnl (float): Profit and Loss value for the chart title.
        """
        # Validate and preprocess data
        self._validate_and_preprocess_data(df, start_date, end_date)
        
        # Create main figure with 2x2 grid
        fig = self._create_main_figure()
        
        # Create the four slots
        self._create_slot1_price_and_volume(fig, df)
        self._create_slot2_placeholder(fig)
        self._create_slot3_candlestick(fig, df)
        self._create_slot4_placeholder(fig)
        
        # Update layout and styling
        self._update_layout(fig, symbol, start_date, end_date, pnl)
        
        # Generate HTML and open in browser
        self._generate_html(fig, symbol, start_date, end_date)
    
    def _validate_and_preprocess_data(self, df, start_date, end_date):
        """Validate input data and preprocess dates."""
        # Validate DataFrame columns
        required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
        if not isinstance(df, pd.DataFrame) or not all(col in df.columns for col in required_cols):
            raise ValueError(f"Data must be a pandas DataFrame with columns: {required_cols}")
        
        # Convert date column to datetime if it's not already
        if not pd.api.types.is_datetime64_any_dtype(df['date']):
            df['date'] = pd.to_datetime(df['date'])
        
        # Filter to date range
        if isinstance(start_date, str):
            start_dt = pd.to_datetime(start_date)
        else:
            start_dt = start_date
            
        if isinstance(end_date, str):
            end_dt = pd.to_datetime(end_date)
        else:
            end_dt = end_date
        
        df_filtered = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)]
        
        if df_filtered.empty:
            raise ValueError(f"No data available for the period {start_date} to {end_date}")
        
        self.df = df_filtered
        self.dates = df_filtered['date'].dt.to_pydatetime()
    
    def _create_main_figure(self):
        """Create the main figure with a 2x2 grid for the dashboard."""
        # Create a figure with 2x2 grid, but set up slot 1 as a subplot area
        fig = make_subplots(
            rows=2, 
            cols=2,
            specs=[
                [{"type": "xy"}, {"type": "xy"}],
                [{"type": "xy"}, {"type": "xy"}]
            ],
            subplot_titles=('Slot 1 (TL)', 'Slot 2 (TR)', 'Slot 3 (BR)', 'Slot 4 (BL)'),
            row_heights=[0.5, 0.5],
            column_widths=[0.5, 0.5],
            vertical_spacing=0.15,
            horizontal_spacing=0.1
        )
        return fig
    
    def _create_slot1_price_and_volume(self, fig, df):
        """Create price action and volume charts for Slot 1 (Top-Left)."""
        # Extract data
        dates = self.dates
        opens = df['open'].values
        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values
        volumes = df['volume'].values
        
        # Create a nested subplot for price and volume in slot 1
        # Use domain to control exact positioning
        volume_height_ratio = 0.25  # 1:3 ratio (volume:price)
        price_height = 1 - volume_height_ratio
        
        # Calculate domains for price and volume charts
        # These will be within the top-left quadrant (0-0.45 horizontally, 0.55-1 vertically)
        price_y_domain = [0.55 + (1-0.55) * (1-price_height), 1]
        volume_y_domain = [0.55, 0.55 + (1-0.55) * (1-price_height) - 0.02]  # 0.02 gap between charts
        
        # Price chart (OHLC candles)
        price_trace = go.Candlestick(
            x=dates,
            open=opens,
            high=highs,
            low=lows,
            close=closes,
            name='OHLC',
            increasing_line_color='green',
            decreasing_line_color='red',
            yaxis='y'
        )
        fig.add_trace(price_trace, row=1, col=1)
        
        # Volume chart (colored by direction)
        buy_sell_colors = ['green' if close >= open else 'red' for open, close in zip(opens, closes)]
        volume_trace = go.Bar(
            x=dates,
            y=volumes,
            marker_color=buy_sell_colors,
            name='Volume',
            yaxis='y2'
        )
        fig.add_trace(volume_trace, row=1, col=1)
        
        # Update axes for slot 1
        fig.update_xaxes(
            title='',  # No title for the shared x-axis within slot 1
            domain=[0, 0.45],
            row=1, col=1
        )
        
        # Update layout to define y-axes positions
        fig.update_layout(
            yaxis=dict(
                title='Price ($)',
                domain=price_y_domain,
                gridcolor='rgba(70,70,70,1)',
                zerolinecolor='rgba(70,70,70,1)'
            ),
            yaxis2=dict(
                title='Volume',
                domain=volume_y_domain,
                gridcolor='rgba(70,70,70,1)',
                zerolinecolor='rgba(70,70,70,1)',
                range=[0, max(volumes) * 1.1]
            )
        )
    
    def _create_slot2_placeholder(self, fig):
        """Create a placeholder chart for Slot 2 (Top-Right)."""
        fig.add_trace(
            go.Scatter(
                x=[0, 1],
                y=[0, 0],
                mode='lines',
                name='Placeholder 2',
                line_color='gray'
            ),
            row=1, col=2
        )
        
        fig.update_xaxes(
            title='Time',
            domain=[0.55, 1],
            row=1, col=2
        )
        
        fig.update_yaxes(
            title='',
            range=[-1, 1],
            domain=[0.55, 1],
            row=1, col=2
        )
    
    def _create_slot3_candlestick(self, fig, df):
        """Create a candlestick chart for Slot 3 (Bottom-Right)."""
        fig.add_trace(
            go.Candlestick(
                x=self.dates,
                open=df['open'].values,
                high=df['high'].values,
                low=df['low'].values,
                close=df['close'].values,
                name='OHLC',
                increasing_line_color='green',
                decreasing_line_color='red'
            ),
            row=2, col=2
        )
        
        fig.update_xaxes(
            title='Time',
            domain=[0.55, 1],
            row=2, col=2
        )
        
        fig.update_yaxes(
            title='Price ($)',
            domain=[0, 0.45],
            row=2, col=2
        )
    
    def _create_slot4_placeholder(self, fig):
        """Create a placeholder chart for Slot 4 (Bottom-Left)."""
        fig.add_trace(
            go.Scatter(
                x=[0, 1],
                y=[0, 0],
                mode='lines',
                name='Placeholder 4',
                line_color='gray'
            ),
            row=2, col=1
        )
        
        fig.update_xaxes(
            title='Time',
            domain=[0, 0.45],
            row=2, col=1
        )
        
        fig.update_yaxes(
            title='',
            range=[-1, 1],
            domain=[0, 0.45],
            row=2, col=1
        )
    
    def _update_layout(self, fig, symbol, start_date, end_date, pnl):
        """Update the dashboard layout and styling."""
        # Define color scheme
        dark_gray = 'rgba(30,30,30,1)'
        light_gray = 'rgba(50,50,50,1)'
        text_color = 'rgba(200,200,200,1)'
        
        # Format dates for title
        if isinstance(start_date, (datetime, pd.Timestamp)):
            start_str = start_date.strftime('%Y-%m-%d')
        else:
            start_str = start_date
            
        if isinstance(end_date, (datetime, pd.Timestamp)):
            end_str = end_date.strftime('%Y-%m-%d')
        else:
            end_str = end_date
        
        # Update overall layout
        fig.update_layout(
            title=f'Dashboard with Backtest {symbol.upper()} | {start_str} - {end_str} | P&L: ${pnl:.2f}',
            paper_bgcolor=dark_gray,
            plot_bgcolor=light_gray,
            font_color=text_color,
            height=800,
            width=1200,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                bgcolor=dark_gray,
                font_color=text_color
            ),
            hovermode="closest"
        )
        
        # Add a time label at the bottom of the figure
        fig.update_layout(
            annotations=[
                dict(
                    x=0.5,
                    y=0,
                    xref="paper",
                    yref="paper",
                    text="Time",
                    showarrow=False,
                    font=dict(color=text_color),
                    bgcolor=dark_gray
                )
            ]
        )
    
    def _generate_html(self, fig, symbol, start_date, end_date):
        """Generate HTML file and open in browser."""
        # Format dates for filename
        if isinstance(start_date, (datetime, pd.Timestamp)):
            start_str = start_date.strftime('%Y%m%d')
        else:
            start_str = start_date.replace('-', '')
            
        if isinstance(end_date, (datetime, pd.Timestamp)):
            end_str = end_date.strftime('%Y%m%d')
        else:
            end_str = end_date.replace('-', '')
        
        # Generate HTML
        html_content = fig.to_html(include_plotlyjs='cdn', full_html=True)
        
        # Save to file
        filename = f"dashboard_{symbol}_{start_str}_{end_str}.html"
        with open(filename, "w") as f:
            f.write(html_content)
        
        # Open in browser
        webbrowser.open(filename, new=2)


# Example usage
if __name__ == "__main__":
    # Create sample data for testing
    dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='D')
    n_days = len(dates)
    
    # Generate realistic price movement data
    base_price = 150
    volatility = 2
    momentum = 0.1
    
    prices = [base_price]
    for _ in range(1, n_days):
        # Add momentum and random component
        change = momentum * (prices[-1] - base_price) + volatility * np.random.randn()
        new_price = prices[-1] + change
        prices.append(new_price)
    
    # Generate OHLC data
    df = pd.DataFrame({
        'date': dates,
        'open': [p * (1 + 0.01 * np.random.randn()) for p in prices],
        'high': [p * (1 + 0.02 + 0.01 * np.random.rand()) for p in prices],
        'low': [p * (1 - 0.02 - 0.01 * np.random.rand()) for p in prices],
        'close': [p * (1 + 0.01 * np.random.randn()) for p in prices],
        'volume': np.random.uniform(1e6, 5e6, n_days)
    })
    
    # Create and display dashboard
    plotter = MultiPlotter()
    plotter.create_dashboard(df, 'PG', '2024-01-01', '2024-12-31', 0.00)