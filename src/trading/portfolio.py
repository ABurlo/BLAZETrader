from flask import Flask, render_template, request, jsonify, redirect, url_for
import json

app = Flask(__name__)

# Mock portfolio data for example
portfolio_data = {
    "AAPL": {
        "shares": 10,
        "price": 150.50,
        "value": 1505.00,
        "change": 2.5
    },
    "TSLA": {
        "shares": 5,
        "price": 800.00,
        "value": 4000.00,
        "change": -1.2
    }
}

demo_balance = 10000.00

# Helper functions
def calculate_total_value():
    return sum(data["value"] for data in portfolio_data.values())

def calculate_total_change():
    if not portfolio_data:
        return "N/A"
    total_value = calculate_total_value()
    if total_value == 0:
        return 0.0
    weighted_change = sum(data["change"] * data["value"] for data in portfolio_data.values())
    return weighted_change / total_value

@app.route('/portfolio', methods=['GET', 'POST'])
def portfolio():
    global portfolio_data, demo_balance
    
    # Handle JSON request for portfolio data
    if request.method == 'GET' and request.headers.get('Accept') == 'application/json':
        return jsonify({
            'portfolio': portfolio_data,
            'total_value': calculate_total_value(),
            'total_change': calculate_total_change(),
            'demo_balance': demo_balance
        })
    
    # Handle form submissions
    if request.method == 'POST':
        # Check if we're expecting JSON response
        is_json_request = request.headers.get('Accept') == 'application/json'
        
        action = request.form.get('action')
        ticker = request.form.get('ticker')
        
        # Process the action
        try:
            if action == 'buy':
                # Buy logic
                shares = int(request.form.get('shares', 0))
                if shares <= 0:
                    raise ValueError("Number of shares must be positive")
                
                # Get current price (in a real app, this would come from a market data API)
                price = portfolio_data.get(ticker, {}).get('price', 100.0)  # Default to $100 if ticker not found
                cost = price * shares
                
                if cost > demo_balance:
                    raise ValueError(f"Insufficient funds. Cost: ${cost:.2f}, Balance: ${demo_balance:.2f}")
                
                # Update portfolio
                if ticker in portfolio_data:
                    portfolio_data[ticker]['shares'] += shares
                    portfolio_data[ticker]['value'] = portfolio_data[ticker]['shares'] * price
                else:
                    portfolio_data[ticker] = {
                        'shares': shares,
                        'price': price,
                        'value': shares * price,
                        'change': 0.0  # New position has no change yet
                    }
                
                # Deduct cost from balance
                demo_balance -= cost
                
            elif action == 'sell':
                # Sell logic
                shares = int(request.form.get('shares', 0))
                if shares <= 0:
                    raise ValueError("Number of shares must be positive")
                
                if ticker not in portfolio_data:
                    raise ValueError(f"You don't own any shares of {ticker}")
                
                if shares > portfolio_data[ticker]['shares']:
                    raise ValueError(f"You only have {portfolio_data[ticker]['shares']} shares of {ticker}")
                
                # Calculate revenue
                price = portfolio_data[ticker]['price']
                revenue = price * shares
                
                # Update portfolio
                portfolio_data[ticker]['shares'] -= shares
                portfolio_data[ticker]['value'] = portfolio_data[ticker]['shares'] * price
                
                # Remove ticker if no shares left
                if portfolio_data[ticker]['shares'] == 0:
                    del portfolio_data[ticker]
                
                # Add revenue to balance
                demo_balance += revenue
                
            elif action == 'force-add':
                # Force add logic
                shares = int(request.form.get('shares', 0))
                current_price = float(request.form.get('current_price', 0))
                cost_basis = float(request.form.get('cost_basis', 0))
                
                if shares <= 0 or current_price <= 0 or cost_basis <= 0:
                    raise ValueError("All values must be positive")
                
                # Calculate change percentage
                change_pct = ((current_price - cost_basis) / cost_basis) * 100
                
                # Update portfolio
                if ticker in portfolio_data:
                    # Average the cost basis if ticker already exists
                    old_shares = portfolio_data[ticker]['shares']
                    old_value = portfolio_data[ticker]['value']
                    new_value = shares * current_price
                    
                    portfolio_data[ticker]['shares'] += shares
                    portfolio_data[ticker]['price'] = current_price
                    portfolio_data[ticker]['value'] = old_value + new_value
                    # Recalculate change based on new average cost
                    portfolio_data[ticker]['change'] = change_pct
                else:
                    portfolio_data[ticker] = {
                        'shares': shares,
                        'price': current_price,
                        'value': shares * current_price,
                        'change': change_pct
                    }
                
            # Prepare response data
            response_data = {
                'portfolio': portfolio_data,
                'total_value': calculate_total_value(),
                'total_change': calculate_total_change(),
                'demo_balance': demo_balance
            }
            
            # Return JSON or redirect based on request type
            if is_json_request:
                return jsonify(response_data)
            else:
                return redirect(url_for('portfolio'))
                
        except ValueError as e:
            error_message = str(e)
            if is_json_request:
                return jsonify({'error': error_message}), 400
            else:
                # In a real app, you might use flash messages here
                return render_template('portfolio.html', 
                                      portfolio=portfolio_data,
                                      total_value=calculate_total_value(),
                                      total_change=calculate_total_change(),
                                      demo_balance=demo_balance,
                                      error=error_message)
        except Exception as e:
            # Log the error in a real app
            error_message = f"An unexpected error occurred: {str(e)}"
            if is_json_request:
                return jsonify({'error': error_message}), 500
            else:
                return render_template('portfolio.html', 
                                      portfolio=portfolio_data,
                                      total_value=calculate_total_value(),
                                      total_change=calculate_total_change(),
                                      demo_balance=demo_balance,
                                      error=error_message)
    
    # GET request - render the template
    return render_template('portfolio.html', 
                          portfolio=portfolio_data,
                          total_value=calculate_total_value(),
                          total_change=calculate_total_change(),
                          demo_balance=demo_balance)

if __name__ == '__main__':
    app.run(debug=True)
