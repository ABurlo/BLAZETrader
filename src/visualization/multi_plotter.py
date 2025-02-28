import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime

class MultiPlotter:
    def create_dashboard(self, df, symbol, start_date, end_date, pnl):
        """
        Create a dashboard with four slots (2x2 grid, clockwise: TL=1, TR=2, BR=3, BL=4) 
        and place the financial chart in Slot 1 (Top-Left), using 1/4 of the user's screen size per slot,
        maximizing size within the slot.
        
        Args:
            df (pd.DataFrame): DataFrame with columns 'date', 'open', 'high', 'low', 'close', 'volume'
            symbol (str): The ticker symbol (e.g., 'MSFT') for the chart title.
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

        # Create a 2x2 subplot grid (clockwise: TL=1, TR=2, BR=3, BL=4)
        fig = make_subplots(rows=2, cols=2, 
                            specs=[[{'type': 'xy'}, {'type': 'xy'}],
                                   [{'type': 'xy'}, {'type': 'xy'}]],
                            subplot_titles=('Slot 1 (TL)', 'Slot 2 (TR)', 'Slot 3 (BR)', 'Slot 4 (BL)'))

        # Slot 1 (Top-Left): Financial Chart (OHLC + Volume)
        fig.add_trace(
            go.Candlestick(x=dates, open=opens, high=highs, low=lows, close=closes, name='OHLC', 
                           increasing_line_color='green', decreasing_line_color='red'),
            row=1, col=1
        )
        fig.add_trace(
            go.Bar(x=dates, y=buy_volumes, name='Buy Volume', marker_color='green'),
            row=1, col=1
        )
        fig.add_trace(
            go.Bar(x=dates, y=sell_volumes, name='Sell Volume', marker_color='red'),
            row=1, col=1
        )

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

        # Update layout for dark gray mode with dynamic sizing (1/4 of screen)
        dark_gray = 'rgba(30,30,30,1)'  # Dark gray background (RGB: 30,30,30)
        light_gray = 'rgba(50,50,50,1)'  # Slightly lighter gray for contrast
        text_color = 'rgba(200,200,200,1)'  # Light gray text for contrast

        # Remove fixed width and height, rely on HTML/JavaScript for dynamic sizing
        fig.update_layout(
            title=f'Dashboard with Backtest {symbol.upper()} | {start_date} - {end_date} | P&L: ${pnl:.2f}',
            paper_bgcolor=dark_gray,  # Dark gray background
            plot_bgcolor=light_gray,  # Slightly lighter gray for plot area
            font_color=text_color,  # Light gray text for contrast
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor=dark_gray, font_color=text_color),
            # No fixed width/height here; handled by HTML/JavaScript
        )

        # Update axes for dark gray mode
        for i in range(1, 3):
            for j in range(1, 3):
                fig.update_yaxes(gridcolor='rgba(70,70,70,1)', zerolinecolor='rgba(70,70,70,1)', showgrid=True, color=text_color, row=i, col=j)
                fig.update_xaxes(gridcolor='rgba(70,70,70,1)', zerolinecolor='rgba(70,70,70,1)', showgrid=True, color=text_color, row=i, col=j)

        # Custom HTML with JavaScript to set 1/4 screen size per slot
        html_content = fig.to_html(include_plotlyjs='cdn', full_html=True)

        # Inject JavaScript to dynamically size the plot to 1/4 of the screen
        html_content = html_content.replace(
            '</head>',
            '''
            <script>
                window.onload = function() {
                    // Get screen dimensions
                    const screenWidth = window.screen.width;
                    const screenHeight = window.screen.height;
                    
                    // Set plot size to 1/4 of screen (2x2 grid)
                    const plotWidth = screenWidth / 2;  // Half width for 2 columns
                    const plotHeight = screenHeight / 2;  // Half height for 2 rows
                    
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

        # Save the custom HTML and open in a new browser window
        with open(f"dashboard_{symbol}_{start_date}_{end_date}.html", "w") as f:
            f.write(html_content)

        # Open the HTML file in a new browser window
        import webbrowser
        webbrowser.open(f"dashboard_{symbol}_{start_date}_{end_date}.html", new=2)  # new=2 opens in a new tab

# Example usage for testing (commented out)
"""
if __name__ == "__main__":
    # Sample data for testing
    sample_data = pd.DataFrame({
        'date': pd.date_range(start='2024-01-01', end='2024-12-31', freq='D'),
        'open': [350.0] * 365,  # Example data for MSFT
        'high': [450.0] * 365,
        'low': [340.0] * 365,
        'close': [400.0] * 365,
        'volume': [20000000] * 365
    })
    multi_plotter = MultiPlotter()
    multi_plotter.create_dashboard(sample_data, 'MSFT', '01/01/2024', '31/12/2024', 0.00)
"""