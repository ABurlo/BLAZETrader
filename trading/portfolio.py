class Portfolio:
    def __init__(self):
        self.balance = 10000.0
        self.positions = {}
        self.pnl = 0.0
        
    def reset(self):
        self.balance = 10000.0
        self.positions = {}
        self.pnl = 0.0
        
    def buy(self, symbol, price, size):
        if symbol not in self.positions:
            self.positions[symbol] = {'quantity': 0, 'entry_price': 0}
        cost = price * size
        if self.balance >= cost:
            self.balance -= cost
            self.positions[symbol]['quantity'] += size
            self.positions[symbol]['entry_price'] = price
    
    def sell(self, symbol, price, size):
        if symbol in self.positions and self.positions[symbol]['quantity'] >= size:
            revenue = price * size
            self.balance += revenue
            self.positions[symbol]['quantity'] -= size
            if self.positions[symbol]['quantity'] == 0:
                del self.positions[symbol]
            entry_price = self.positions.get(symbol, {}).get('entry_price', price)
            trade_pnl = (price - entry_price) * size
            self.pnl += trade_pnl
            return trade_pnl > 0
        return False
    
    def update(self, current_price):
        unrealized_pnl = 0
        for symbol, pos in self.positions.items():
            unrealized_pnl += (current_price - pos['entry_price']) * pos['quantity']
        self.pnl = unrealized_pnl
    
    def get_pnl(self):
        return self.pnl