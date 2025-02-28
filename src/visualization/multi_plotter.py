import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime
import webbrowser
import os
import time

class MultiPlotter:
    def create_dashboard(self, df, symbol, start_date, end_date, pnl):
        """
        Create a dashboard with four slots (2x2 grid, clockwise: TL=1, TR=2, BR=3, BL=4) 
        and place the financial chart in Slot 1 (Top-Left), using 1/4 of the user's screen size per slot,
        maximizing size within the slot.
        
        Args:
            df (pd.DataFrame): DataFrame with columns 'date', 'open', 'high', 'low', 'close', 'volume'
            symbol (str): The ticker symbol (e.g., 'AMZN') for the chart title.
            start_date (str): Start date in 'DD/MM/YYYY' format.
            end_date (str): End date in 'DD/MM/YYYY' format.
            pnl (float): Profit and Loss value for the chart title.
        """
        # Ensure data is in the correct format
        if not isinstance(df, pd.DataFrame):
            raise ValueError("Data must be a pandas DataFrame with columns 'date', 'open', 'high', 'low', 'close', 'volume'")
        
        # Convert date strings to datetime if not already
        if not pd.api.types.is_datetime64_any_dtype(df['date']):
            df['date'] = pd.to_datetime(df['date'], format='%d/%m/%Y')

        # Filter data to match the backtest period (start_date to end_date)
        start_dt = pd.to_datetime(start_date, format='%d/%m/%Y')
        end_dt = pd.to_datetime(end_date, format='%d/%m/%Y')
        df = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)].copy()

        # Extract data for the financial chart
        dates = df['date'].dt.to_pydatetime()
        opens = df['open'].values
        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values
        volumes = df['volume'].values

        # Infer buy/sell volume based on candle direction (approximation)
        buy_volumes = []
        sell_volumes = []
        for open_price, close_price, volume in zip(opens, closes, volumes):
            if close_price > open_price:  # Upward candle = buy volume
                buy_volumes.append(volume)
                sell_volumes.append(0)
            elif close_price < open_price:  # Downward candle = sell volume
                buy_volumes.append(0)
                sell_volumes.append(volume)
            else:  # No change, split evenly
                buy_volumes.append(volume / 2)
                sell_volumes.append(volume / 2)

        # Create a 2x2 subplot grid for Slot 1 (TL) with custom row heights: 2/3 for OHLC, 1/3 for volume
        fig = make_subplots(rows=2, cols=2, 
                            specs=[[{'type': 'xy'}, {'type': 'xy'}],  # Top row: TL and TR
                                   [{'type': 'xy'}, {'type': 'xy'}]],  # Bottom row: BL and BR
                            subplot_titles=('Slot 1 (TL)', 'Slot 2 (TR)', 'Slot 4 (BL)', 'Slot 3 (BR)'),
                            row_heights=[0.667, 0.333],  # 2/3 for OHLC, 1/3 for volume in Slot 1
                            vertical_spacing=0.05,  # Tighter spacing for better fit
                            shared_xaxes=True)  # Share x-axes across subplots in Slot 1

        # Slot 1 (Top-Left): OHLC Candlestick (Top 2/3) and Volume (Bottom 1/3)
        # OHLC Candlestick in the top 2/3 (row 1, col 1)
        fig.add_trace(
            go.Candlestick(x=dates, open=opens, high=highs, low=lows, close=closes, name='OHLC', 
                           increasing_line_color='green', decreasing_line_color='red'),
            row=1, col=1
        )

        # Volume bars in the bottom 1/3 (row 2, col 1), with buy (green) and sell (red)
        fig.add_trace(
            go.Bar(x=dates, y=buy_volumes, name='Buy Volume', marker_color='green'),
            row=2, col=1
        )
        fig.add_trace(
            go.Bar(x=dates, y=sell_volumes, name='Sell Volume', marker_color='red'),
            row=2, col=1
        )

        # Lock the x-axis range to the backtest period (start_dt to end_dt) for Slot 1
        fig.update_xaxes(range=[start_dt, end_dt], row=1, col=1)  # OHLC x-axis
        fig.update_xaxes(range=[start_dt, end_dt], row=2, col=1, showticklabels=True)  # Volume x-axis with labels

        # Hide x-axis labels for the OHLC subplot to avoid duplication
        fig.update_xaxes(showticklabels=False, row=1, col=1)

        # Adjust y-axis titles and margins to ensure clear separation
        fig.update_yaxes(title_text="Price", row=1, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1)

        # Slot 2 (Top-Right): Placeholder (e.g., empty plot or simple line)
        fig.add_trace(
            go.Scatter(x=[0, 1], y=[0, 1], mode='lines', name='Placeholder 2', line_color='gray'),
            row=1, col=2
        )

        # Slot 3 (Bottom-Right): Placeholder (e.g., empty plot or simple line)
        fig.add_trace(
            go.Scatter(x=[0, 1], y=[0, 1], mode='lines', name='Placeholder 3', line_color='gray'),
            row=2, col=2
        )

        # Slot 4 (Bottom-Left): Placeholder (e.g., empty plot or simple line)
        fig.add_trace(
            go.Scatter(x=[0, 1], y=[0, 1], mode='lines', name='Placeholder 4', line_color='gray'),
            row=2, col=1
        )

        # Lock the x-axis range to the backtest period for Slot 4
        fig.update_xaxes(range=[start_dt, end_dt], row=2, col=1)

        # Update layout for dark gray mode with dynamic sizing (1/4 of screen), accounting for high-DPI
        dark_gray = 'rgba(30,30,30,1)'  # Dark gray background (RGB: 30,30,30)
        light_gray = 'rgba(50,50,50,1)'  # Slightly lighter gray for contrast
        text_color = 'rgba(200,200,200,1)'  # Light gray text for contrast

        fig.update_layout(
            title=f'Dashboard with Backtest {symbol.upper()} | {start_date} - {end_date} | P&L: ${pnl:.2f}',
            paper_bgcolor=dark_gray,  # Dark gray background
            plot_bgcolor=light_gray,  # Slightly lighter gray for plot area
            font_color=text_color,  # Light gray text for contrast
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor=dark_gray, font_color=text_color),
            margin=dict(l=50, r=50, t=80, b=50),  # Adjust margins for better fit on high-DPI
            # No fixed width/height here; handled by HTML/JavaScript
        )

        # Update axes for dark gray mode and ensure proper alignment
        for i in range(1, 3):
            for j in range(1, 3):
                fig.update_yaxes(gridcolor='rgba(70,70,70,1)', zerolinecolor='rgba(70,70,70,1)', showgrid=True, color=text_color, row=i, col=j)
                fig.update_xaxes(gridcolor='rgba(70,70,70,1)', zerolinecolor='rgba(70,70,70,1)', showgrid=True, color=text_color, row=i, col=j)

        # Custom HTML with JavaScript to set 1/4 screen size per slot, accounting for high-DPI
        html_content = fig.to_html(include_plotlyjs='cdn', full_html=True)

        # Inject JavaScript to dynamically size the plot to 1/4 of the screen, considering device pixel ratio
        html_content = html_content.replace(
            '</head>',
            '''
            <script>
                window.onload = function() {
                    // Get screen dimensions and device pixel ratio for high-DPI (e.g., Retina displays)
                    const screenWidth = window.screen.width * window.devicePixelRatio;
                    const screenHeight = window.screen.height * window.devicePixelRatio;
                    
                    // Set plot size to 1/4 of screen (2x2 grid), adjusted for DPI
                    const plotWidth = (screenWidth / 2) / window.devicePixelRatio;  // Half width for 2 columns, scaled down
                    const plotHeight = (screenHeight / 2) / window.devicePixelRatio;  // Half height for 2 rows, scaled down
                    
                    // Apply size to the div containing the plot
                    document.getElementById('plot').style.width = plotWidth + 'px';
                    document.getElementById('plot').style.height = plotHeight + 'px';
                    
                    // Ensure each subplot (slot) takes full space within the plot div
                    const subplots = document.querySelectorAll('.subplot');
                    subplots.forEach(subplot => {
                        subplot.style.width = '100%';
                        subplot.style.height = '100%';
                    });
                    
                    // Position the plot div in the top-left (Slot 1)
                    document.getElementById('plot').style.position = 'absolute';
                    document.getElementById('plot').style.top = '0';
                    document.getElementById('plot').style.left = '0';
                };
            </script>
            </head>
            '''
        )

        # Generate the filename
        filename = f"dashboard_{symbol}_{start_date}_{end_date}.html"
        
        # Save the custom HTML
        with open(filename, "w") as f:
            f.write(html_content)

        # Wait briefly to ensure the file is fully written
        time.sleep(0.5)

        # Check if the file exists and open it automatically in the default web browser
        if os.path.exists(filename):
            webbrowser.open(filename, new=2)  # new=2 opens in a new tab
        else:
            print(f"Error: Could not find file {filename} to open.")

# Example usage for testing (commented out)
"""
if __name__ == "__main__":
    # Sample data for testing
    sample_data = pd.DataFrame({
        'date': pd.date_range(start='2024-01-01', end='2024-12-31', freq='D'),
        'open': [350.0] * 365,  # Example data for AMZN
        'high': [450.0] * 365,
        'low': [340.0] * 365,
        'close': [400.0] * 365,
        'volume': [20000000] * 365
    })
    multi_plotter = MultiPlotter()
    multi_plotter.create_dashboard(sample_data, 'AMZN', '01/01/2024', '31/12/2024', 0.00)
"""