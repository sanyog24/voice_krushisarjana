from flask import Flask, request, jsonify
from flask_cors import CORS  # Import CORS
import pandas as pd
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Load data from the Excel file
def load_data():
    try:
        df = pd.read_excel('Price_Agriculture_commodities_Week.xlsx')
        return df
    except Exception as e:
        raise Exception(f"Failed to load Excel file: {e}")

# Train model and predict price
def predict_price(commodity):
    try:
        df = load_data()
        df['Arrival_Date'] = pd.to_datetime(df['Arrival_Date'], format='%d-%m-%Y', errors='coerce')
        df.dropna(subset=['Arrival_Date'], inplace=True)
        df = df.sort_values(by='Arrival_Date')

        # Feature Engineering
        df['Year'] = df['Arrival_Date'].dt.year
        df['Month'] = df['Arrival_Date'].dt.month
        df['Day'] = df['Arrival_Date'].dt.day

        # Filter data for the selected commodity
        df_filtered = df[df['Commodity'] == commodity]
        if df_filtered.empty:
            return {"error": f"No data available for {commodity}."}

        # Train model
        features = ['Year', 'Month', 'Day', 'Min Price', 'Max Price']
        target = 'Modal Price'
        X = df_filtered[features]
        y = df_filtered[target]

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X_train, y_train)

        # Predict price for tomorrow
        tomorrow = datetime.today() + timedelta(days=1)
        last_row = df_filtered.iloc[-1]
        min_price = last_row['Min Price']
        max_price = last_row['Max Price']

        input_data = pd.DataFrame([[tomorrow.year, tomorrow.month, tomorrow.day, min_price, max_price]],
                                  columns=['Year', 'Month', 'Day', 'Min Price', 'Max Price'])
        predicted_price = model.predict(input_data)[0]

        # Determine unit based on commodity type
        quintal_commodities = {'Wheat', 'Rice', 'Maize', 'Barley', 'Pulses', 'Jowar', 'Bajra', 'Gram'}
        kg_commodities = {'Potato', 'Onion', 'Tomato', 'Apple', 'Banana', 'Mango', 'Chili', 'Ginger'}
        if commodity in quintal_commodities:
            predicted_price /= 100  # Convert ₹ per quintal to ₹ per kg
            unit = "kg"
        elif commodity in kg_commodities:
            predicted_price /= 10
            unit = "kg"
        else:
            unit = "quintal"

        # Get historical data for the last 7 days
        historical_data = df_filtered[['Arrival_Date', 'Modal Price']].tail(7)
        historical_data['Arrival_Date'] = historical_data['Arrival_Date'].dt.strftime('%Y-%m-%d')

        # Add predicted price to historical data
        predicted_data = {
            "Arrival_Date": tomorrow.strftime('%Y-%m-%d'),
            "Modal Price": predicted_price
        }
        historical_data = pd.concat([historical_data, pd.DataFrame([predicted_data])], ignore_index=True)

        return {
            "commodity": commodity,
            "predicted_price": predicted_price,
            "unit": unit,
            "historical_data": historical_data.to_dict(orient='records')
        }
    except Exception as e:
        raise Exception(f"Failed to predict price: {e}")

# API endpoint to predict price
@app.route('/predict', methods=['GET'])
def predict():
    try:
        commodity = request.args.get('commodity')
        if not commodity:
            return jsonify({"error": "Commodity parameter is required."}), 400
        
        result = predict_price(commodity)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Default route for debugging
@app.route('/')
def home():
    return "Flask server is running!"

# Run the Flask app
if __name__ == '__main__':
    app.run(port=5001, debug=True)