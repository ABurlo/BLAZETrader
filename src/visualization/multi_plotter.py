import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime
import webbrowser

class MultiPlotter:
    def create_dashboard(self, df, symbol, start_date, end_date, pnl):
        """
        Create a dashboard with four slots (2x2 grid, clockwise: TL=1, TR=2, BR=3, BL=4) 
        and place the financial chart in Slot 1 (Top-Left), using 1/4 of the user's screen size per slot,
        maximizing size within the slot.
        
        Args:
            df (pd.DataFrame): DataFrame with columns 'date', 'open', 'high', 'low', 'close', 'volume'
            symbol (str): The ticker symbol (e.g., 'MSFT') for the chart title.
            start_date (str or datetime): Start date in 'DD/MM/YYYY' format or datetime object.
            end_date (str or datetime): End date in 'DD/MM/YYYY' format or datetime object.
            pnl (float): Profit and Loss value for the chart title.
        """
        # Ensure data is in the correct format
        if not isinstance(df, pd.DataFrame) or not all(col in df.columns for col in ['date', 'open', 'high', 'low', 'close', 'volume']):
            raise ValueError("Data must be a pandas DataFrame with columns 'date', 'open', 'high', 'low', 'close', 'volume'")
        
        # Convert date strings to datetime if not already
        if not pd.api.types.is_datetime64_any_dtype(df['date']):
            df['date'] = pd.to_datetime(df['date'], format='%d/%m/%Y')

        # Handle start_date and end_date (convert to datetime if strings, or use as-is if already datetime)
        if isinstance(start_date, str):
            start_dt = datetime.strptime(start_date, '%d/%m/%Y')
        else:
            start_dt = start_date

        if isinstance(end_date, str):
            end_dt = datetime.strptime(end_date, '%d/%m/%Y')
        else:
            end_dt = end_date

        # Filter the DataFrame to only include data within the backtest period
        df = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)]

        # Check if the filtered DataFrame is empty
        if df.empty:
            raise ValueError(f"No data available for the period {start_date} to {end_date}")

        # Extract data for the financial chart (only within the backtest period)
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

        # Create a 2x2 subplot grid with custom row heights
        # Allocate 60% of the height to row 1 (for Slot 1 and Slot 2, including volume in Slot 1)
        # Allocate 40% of the height to row 2 (split evenly between Slot 3 and Slot 4)
        fig = make_subplots(rows=2, cols=2, 
                            specs=[[{'type': 'xy'}, {'type': 'xy'}],
                                   [{'type': 'xy'}, {'type': 'xy'}]],
                            subplot_titles=('Slot 1 (TL)', 'Slot 2 (TR)', 'Slot 3 (BR)', 'Slot 4 (BL)'),
                            row_heights=[0.35, 0.65],  # 60% for row 1, 40% for row 2
                            vertical_spacing=0.5,  # Adjust vertical spacing to prevent overlap
                            horizontal_spacing=0.1)  # Adjust horizontal spacing for better layout

        # Slot 1 (Top-Left): OHLC Candles with Volume on secondary y-axis (stacked vertically)
        fig.add_trace(
            go.Candlestick(x=dates, open=opens, high=highs, low=lows, close=closes, name='OHLC', 
                           increasing_line_color='green', decreasing_line_color='red'),
            row=1, col=1
        )
        fig.add_trace(
            go.Bar(x=dates, y=buy_volumes, name='Buy Volume', marker_color='green', yaxis='y2'),
            row=1, col=1
        )
        fig.add_trace(
            go.Bar(x=dates, y=sell_volumes, name='Sell Volume', marker_color='red', yaxis='y2'),
            row=1, col=1
        )

        # Slot 2 (Top-Right): Placeholder (e.g., empty plot or simple line)
        fig.add_trace(
            go.Scatter(x=[0, 1], y=[0, 1], mode='lines', name='Placeholder 2', line_color='gray'),
            row=1, col=2
        )

        # Slot 3 (Bottom-Right): Placeholder starting at y=0 (e.g., empty plot or simple line starting at zero)
        fig.add_trace(
            go.Scatter(x=[0, 1], y=[0, 1], mode='lines', name='Placeholder 3', line_color='gray'),
            row=2, col=2
        )

        # Slot 4 (Bottom-Left): Placeholder starting at y=0 (e.g., empty plot or simple line starting at zero)
        fig.add_trace(
            go.Scatter(x=[0, 1], y=[0, 1], mode='lines', name='Placeholder 4', line_color='gray'),
            row=2, col=1
        )

        # Update layout for dark gray mode with dynamic sizing (1/4 of screen)
        dark_gray = 'rgba(30,30,30,1)'  # Dark gray background (RGB: 30,30,30)
        light_gray = 'rgba(50,50,50,1)'  # Slightly lighter gray for contrast
        text_color = 'rgba(200,200,200,1)'  # Light gray text for contrast

        fig.update_layout(
            title=f'Dashboard with Backtest {symbol.upper()} | {start_date} - {end_date} | P&L: ${pnl:.2f}',
            paper_bgcolor=dark_gray,  # Dark gray background
            plot_bgcolor=light_gray,  # Slightly lighter gray for plot area
            font_color=text_color,  # Light gray text for contrast
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor=dark_gray, font_color=text_color),
            height=800,  # Set a reasonable height to allow scrolling if content exceeds screen size
            yaxis2=dict(overlaying='y', side='right', title='Volume', showgrid=False)  # Secondary y-axis for volume
        )

        # Update axes for dark gray mode, ensure Slot 3 and 4 start at y=0
        for i in range(1, 3):
            for j in range(1, 3):
                fig.update_xaxes(
                    gridcolor='rgba(70,70,70,1)', 
                    zerolinecolor='rgba(70,70,70,1)', 
                    showgrid=True, 
                    color=text_color, 
                    row=i, 
                    col=j
                )
                fig.update_yaxes(
                    gridcolor='rgba(70,70,70,1)', 
                    zerolinecolor='rgba(70,70,70,1)', 
                    showgrid=True, 
                    color=text_color, 
                    range=[0, None] if i == 2 else None,  # Force y-axis to start at 0 for rows 2 (Slot 3 and 4)
                    row=i, 
                    col=j
                )

        # Custom HTML with JavaScript to set 1/4 screen size per slot, allow scrolling
        html_content = fig.to_html(include_plotlyjs='cdn', full_html=True)

        # Inject JavaScript to dynamically size the plot to 1/4 of the screen and enable scrolling if needed
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
                    const plotDiv = document.getElementById('plot');
                    plotDiv.style.width = plotWidth + 'px';
                    plotDiv.style.height = plotHeight + 'px';
                    plotDiv.style.overflow = 'auto';  // Allow scrolling if content exceeds size
                    
                    // Ensure each subplot (slot) takes full space within the plot div
                    const subplots = document.querySelectorAll('.subplot');
                    subplots.forEach(subplot => {
                        subplot.style.width = '100%';
                        subplot.style.height = '100%';
                    });
                    
                    // Position the plot div in the top-left (Slot 1)
                    plotDiv.style.position = 'absolute';
                    plotDiv.style.top = '0';
                    plotDiv.style.left = '0';
                };
            </script>
            </head>
            '''
        )

        # Save the custom HTML and open in a new browser window
        with open(f"dashboard_{symbol}_{start_date}_{end_date}.html", "w") as f:
            f.write(html_content)

        # Open the HTML file in a new browser window
        webbrowser.open(f"dashboard_{symbol}_{start_date}_{end_date}.html", new=2)  # new=2 opens in a new tab

# Example usage
if __name__ == "__main__":
    df = pd.DataFrame({
        'date': ['01/01/2025', '02/01/2025', '03/01/2025'],
        'open': [100, 102, 101],
        'high': [103, 104, 102],
        'low': [99, 100, 99],
        'close': [102, 101, 100],
        'volume': [1000, 1500, 1200]
    })
    plotter = MultiPlotter()
    plotter.create_dashboard(df, 'MSFT', '01/01/2025', '03/01/2025', 500.25)