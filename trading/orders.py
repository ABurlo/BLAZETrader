from ib_insync import Order, Stock

class OrderManager:
    def __init__(self, ib):
        self.ib = ib
        
    def place_market_order(self, symbol, action, quantity):
        contract = Stock(symbol, 'SMART', 'USD')
        self.ib.qualifyContracts(contract)
        order = Order()
        order.action = action
        order.orderType = 'MKT'
        order.totalQuantity = quantity
        trade = self.ib.placeOrder(contract, order)
        return trade