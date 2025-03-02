import tkinter as tk
from tkinter import ttk
from src.trading.engine import TradingEngine

class BlazeTraderUI:
    def __init__(self, root):
        self.root = root
        self.root.title("BLAZETrader")
        self.root.geometry("1200x800")
        self.engine = TradingEngine()

        # Main layout
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill="both", expand=True)

        # Left: Placeholder for chart
        self.chart_frame = tk.Frame(self.main_frame, width=800, height=800, bg="gray")
        self.chart_frame.pack(side="left", fill="both", expand=True)

        # Right: PNL and Trade Log
        self.right_frame = tk.Frame(self.main_frame, width=400)
        self.right_frame.pack(side="right", fill="y")

        # PNL Panel
        self.pnl_frame = tk.LabelFrame(self.right_frame, text="PNL", padx=10, pady=10)
        self.pnl_frame.pack(fill="x", pady=(0, 10))
        self.pnl_labels = {}
        for metric in ["Total Value", "P/L $", "P/L %"]:
            label = tk.Label(self.pnl_frame, text=f"{metric}: ", font=("Arial", 12))
            label.pack(anchor="w")
            self.pnl_labels[metric] = label

        # Trade Log Panel
        self.trade_frame = tk.LabelFrame(self.right_frame, text="Trade Log", padx=10, pady=10)
        self.trade_frame.pack(fill="both", expand=True)
        self.trade_tree = ttk.Treeview(self.trade_frame, columns=("Date", "Type", "Price", "Shares"), show="headings")
        self.trade_tree.heading("Date", text="Date")
        self.trade_tree.heading("Type", text="Type")
        self.trade_tree.heading("Price", text="Price")
        self.trade_tree.heading("Shares", text="Shares")
        self.trade_tree.pack(fill="both", expand=True)

        # Server Logs (bottom)
        self.log_frame = tk.LabelFrame(self.root, text="Server Logs", padx=10, pady=10)
        self.log_frame.pack(fill="x", side="bottom")
        self.log_text = tk.Text(self.log_frame, height=5)
        self.log_text.pack(fill="x")

    async def run_backtest(self, symbol, start_date, end_date, timeframe="1 day"):
        await self.engine.initialize()
        df, pnl, trades, pnl_history = self.engine.run_backtest(symbol, start_date, end_date, timeframe)

        if df is not None:
            # Update PNL
            initial_capital = 10000  # Default from your portfolio reset
            final_value = pnl_history[-1]['total_value'] if pnl_history else initial_capital
            pl_dollar = final_value - initial_capital
            pl_percent = (pl_dollar / initial_capital) * 100

            self.pnl_labels["Total Value"].config(text=f"Total Value: ${final_value:.2f}", fg="green" if pl_dollar >= 0 else "red")
            self.pnl_labels["P/L $"].config(text=f"P/L $: ${pl_dollar:.2f}", fg="green" if pl_dollar >= 0 else "red")
            self.pnl_labels["P/L %"].config(text=f"P/L %: {pl_percent:.2f}%", fg="green" if pl_percent >= 0 else "red")

            # Update Trade Log
            for trade in trades:
                self.trade_tree.insert("", "end", values=(trade['date'], trade['type'], f"${trade['price']:.2f}", trade['shares']))

            # Log completion
            self.log_text.insert(tk.END, f"Backtest completed for {symbol}. PNL: ${pnl:.2f}\n")
            self.log_text.see(tk.END)

if __name__ == "__main__":
    import asyncio
    root = tk.Tk()
    ui = BlazeTraderUI(root)
    asyncio.run(ui.run_backtest("AAPL", "2023-01-01", "2023-12-31"))
    root.mainloop()