from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import pandas as pd
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
import speech_recognition as sr
from gtts import gTTS
import os
import tempfile
import pygame
try:
    import google.generativeai as genai
except (ImportError, AttributeError) as e:
    print(f"Warning: Could not import google.generativeai: {e}")
    print("Please run: pip install --upgrade google-generativeai protobuf==4.24.0")
    genai = None
from deep_translator import GoogleTranslator
import time
import nltk
from nltk.stem import WordNetLemmatizer
import threading
import queue
import re
import logging

# Global variables to track voice assistant state and button press count
voice_assistant_active = False
result_queue = queue.Queue()
frontend_products_data = []

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["http://localhost:3000", "https://krushi-sarjana.vercel.app"]}})
socketio = SocketIO(app, cors_allowed_origins=["http://localhost:3000", "https://krushi-sarjana.vercel.app"])

# Configure Gemini API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")
if genai is not None:
    genai.configure(api_key=GEMINI_API_KEY)
translator = GoogleTranslator()

# Download NLTK data
nltk.download('wordnet')
lemmatizer = WordNetLemmatizer()

# Function to play speech
def speak(text, lang):
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        tts = gTTS(text, lang=lang, slow=False)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as fp:
            temp_path = fp.name
            tts.save(temp_path)
        pygame.mixer.music.load(temp_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            continue
        pygame.mixer.quit()
        time.sleep(1)
        os.remove(temp_path)
    except Exception as e:
        print(f"Error in speak function: {e}")

# Function to recognize speech
def recognize_speech(language):
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)
    try:
        text = recognizer.recognize_google(audio, language=language)
        return text.lower()
    except sr.UnknownValueError:
        return "Sorry, I could not understand."
    except sr.RequestError:
        return "Request error from Google API."

# Get Gemini AI response
def get_gemini_response(prompt):
    if genai is None:
        return "Gemini API is not available. Please install google-generativeai properly."
    model = genai.GenerativeModel("gemini-pro")
    response = model.generate_content(prompt)
    return response.text

# Function to extract preferences
def extract_preferences(query, preferences):
    query = query.lower()
    words = [lemmatizer.lemmatize(word) for word in query.split()]

    pesticide_words = ["pesticide", "pesticides", "कीटनाशक", "कीटकनाशक", "कीटनाशक दवा"]
    seed_words = ["seed", "seeds", "बीज", "बियाणे", "bich", "बीच", "बी"]
    equipment_words = ["equipment", "equipments", "उपकरण", "उपकरणे"]

    if any(word in pesticide_words for word in words):
        preferences["category"] = "pesticide"
    elif any(word in seed_words for word in words):
        preferences["category"] = "seed"
    elif any(word in equipment_words for word in words):
        preferences["category"] = "equipment"

    print(f"Extracted Category Preference: {preferences.get('category')}")
    return preferences

import re

def extract_price_regex(query):
    price_limit = None
    price_query_part = query.lower()

    # Corrected regex to capture prices in thousands and decimals
    price_regex = r'(\d[\d,.]*)'
    price_numbers = re.findall(price_regex, price_query_part)

    if price_numbers:
        price_str = price_numbers[0].replace(",", "")
        try:
            price_limit = float(price_str)
            print(f"Extracted Price (Regex): {price_limit}")
        except ValueError:
            print(f"Warning: Could not convert extracted price string '{price_str}' to a number.")
    
    return price_limit


# Recommend products based on preferences
def recommend_products(preferences):
    global frontend_products_data
    recommendations = []

    print("\n--- Inside recommend_products ---")
    print("Preferences:", preferences)
    print("Frontend Product Data:", frontend_products_data)

    if frontend_products_data:
        for product in frontend_products_data:
            product_category = product.get("category", "").lower().strip()
            pref_category = preferences.get("category", "").lower().strip()
            product_price = product.get("price", 0)
            max_price_pref = preferences.get("max_price")

            print(f"Checking Product: {product.get('name')}, Category: {product_category}, Price: {product_price}")

            # Improved category matching: handle singular/plural forms and exact matches
            category_match = (
                product_category == pref_category or
                product_category == pref_category + 's' or
                pref_category == product_category + 's' or
                product_category.startswith(pref_category)
            )
            
            price_match = True
            if max_price_pref is not None:
                price_match = product_price <= max_price_pref

            if category_match and price_match:
                recommendations.append({"name": product.get("name"), "price": product_price, "image": product.get("image")})
                print("  ✓ Match found (Category & Price)! Processing for frontend.")
            elif category_match:
                print(f"  ✓ Category match found, but price {product_price} exceeds limit {max_price_pref}")
            else:
                print(f"  ✗ No category match: '{product_category}' != '{pref_category}'")

    else:
        print("Warning: No product data received from frontend yet.")

    print("Recommendations (formatted for frontend):", recommendations)
    print("--- End recommend_products ---\n")
    return recommendations

# Voice-based interaction
def voice_interaction():
    global voice_assistant_active

    selected_language = None
    preferences = {"category": None, "type": None, "max_price": None}
    exit_keywords = ["exit", "quit", "बंद करो", "बंद करें", "बाहर जाएं", "बाहेर जा"]
    goodbye_messages = {
        "en": "Goodbye!",
        "hi": "अलविदा!",
        "mr": "अलविदा!",
    }
    language_prompts = {
        "en": "Hello Shetkari! Please choose a language: English, Hindi, Marathi",
        "hi": "नमस्ते शेतकरी! कृपया भाषा चुनें: अंग्रेजी, हिंदी, मराठी",
        "mr": "नमस्कार शेतकरी! कृपया भाषा निवडा: इंग्रजी, हिंदी, मराठी"
    }
    category_prompts = {
        "en": "Please specify category: Seed, Pesticide, or Equipment?",
        "hi": "नमस्ते! मैं आपकी कैसे सहायता कर सकती हूँ? ",
        "mr": "नमस्कार! मी तुम्हाला काय मदत करू शकते?"
    }
    price_prompt = {
        "en": "What's your price limit?", # या "What's the maximum price you're looking at?"
        "hi": "आप ज़्यादा से ज़्यादा कितने रुपये तक का देखना चाहते हैं?", # या "कितने रुपये तक का चलेगा?"
        "mr": "तुम्हाला किती पर्यंतची किंमत चालेल?" # या "जास्तीत जास्त किती किमती पर्यंत बघताय?"
}

    try:
        while voice_assistant_active:
            print("Voice Interaction Loop: voice_assistant_active =", voice_assistant_active)
            if not selected_language:
                print(language_prompts["en"])
                speak(language_prompts["en"], "en")
                language = recognize_speech("en").lower()
                if any(word in language for word in exit_keywords):
                    print("Exiting due to language exit keyword...")
                    goodbye_message = goodbye_messages.get("en", "Goodbye!")
                    speak(goodbye_message, "en")
                    result_queue.put({"message": "Voice assistant exited."})
                    break
                lang_code = {"english": "en", "hindi": "hi", "marathi": "mr"}.get(language, "en")
                selected_language = lang_code
                print(f"Selected Language: {language.capitalize()} ({selected_language})")
                if not voice_assistant_active:
                    print("Voice assistant stopped after language selection.")
                    break

            if not voice_assistant_active:
                print("Voice assistant stopped before user query.")
                break

            speak(category_prompts[selected_language], selected_language)
            user_query_category = recognize_speech(selected_language)

            if not voice_assistant_active:
                print("Voice assistant stopped after category query recognition.")
                break

            if any(word in user_query_category for word in exit_keywords):
                print("Exiting due to user query exit keyword...")
                goodbye_message = goodbye_messages.get(selected_language, "Goodbye!")
                speak(goodbye_message, selected_language)
                result_queue.put({"message": "Voice assistant exited."})
                break

            print(f"User Query (Category): {user_query_category}")

            detected_lang_cat = GoogleTranslator(source='auto', target=selected_language).translate(user_query_category)
            if detected_lang_cat:
                user_query_category = detected_lang_cat

            preferences = extract_preferences(user_query_category, preferences)

            if not preferences["category"]:
                speak(
                    "कृपया श्रेणी निर्दिष्ट करें। बीज, कीटनाशक, या उपकरण?" if selected_language == "hi" else "कृपया श्रेणी निर्दिष्ट करा. बियाणे, कीटकनाशक किंवा उपकरण?" if selected_language == "mr" else "Please specify category: Seed, Pesticide, or Equipment?",
                    selected_language)
                continue

            speak(price_prompt[selected_language], selected_language)
            user_query_price = recognize_speech(selected_language)
            print(f"User Query (Price): {user_query_price}")

            if any(word in user_query_price for word in exit_keywords):
                print("Exiting during price input...")
                goodbye_message = goodbye_messages.get(selected_language, "Goodbye!")
                speak(goodbye_message, selected_language)
                result_queue.put({"message": "Voice assistant exited."})
                voice_assistant_active = False
                return

            detected_lang_price = GoogleTranslator(source='auto', target=selected_language).translate(user_query_price)
            if detected_lang_price:
                user_query_price = detected_lang_price

            extracted_price = extract_price_regex(user_query_price)
            if extracted_price is not None:
                preferences["max_price"] = extracted_price
            else:
                print("Price not understood, proceeding without price preference.")
                speak("Price not understood. Proceeding without price preference.", selected_language)

            recommendations = recommend_products(preferences)

            if recommendations:
                response_text_list = []
                for product in recommendations:
                    response_text_product = (
                        f"{product.get('name', 'N/A')} के लिए {product.get('price', 'N/A')} रुपये" if selected_language == "hi" else
                        f"{product.get('name', 'N/A')} साठी {product.get('price', 'N/A')} रुपये" if selected_language == "mr" else
                        f"{product.get('name', 'N/A')} for {product.get('price', 'N/A')} rupees"
                    )
                    response_text_list.append(response_text_product)

                response = "मैं निम्नलिखित उत्पादों की सिफारिश कर रही हूँ:\n" if selected_language == "hi" else "मी खालील उत्पादने शिफारस करत आहे:\n" if selected_language == "mr" else "I recommend the following products:\n"
                response += "\n".join(response_text_list)

            else:
                response = "माफ करें, आपकी पसंद के लिए कोई उत्पाद नहीं मिला।" if selected_language == "hi" else "माफ करा, तुमच्या पसंतीसाठी कोणतेही उत्पादन आढळले नाही." if selected_language == "mr" else "Sorry, no products found for your preference."

            print(f"Assistant Response: {response}")

            result_queue.put({"recommendations": recommendations, "full_response_text": response})
            break

    except Exception as e:
        result_queue.put({"error": str(e)})
    finally:
        voice_assistant_active = False
        print("Voice Interaction Thread finished. voice_assistant_active =", voice_assistant_active)

# API endpoint to stop voice assistant
@app.route('/stop_voice_assistant', methods=['GET'])
def stop_voice_assistant():
    global voice_assistant_active
    print("Endpoint /stop_voice_assistant hit!")
    voice_assistant_active = False
    print("Set voice_assistant_active to False in /stop_voice_assistant")
    result_queue.put({"message": "Voice assistant stopped by user."})
    return jsonify({"message": "Voice assistant stopped."})

# API endpoint to start voice interaction
@app.route('/voice', methods=['GET'])
def voice():
    global voice_assistant_active
    try:
        if not voice_assistant_active:
            voice_assistant_active = True
            threading.Thread(target=voice_interaction).start()
            return jsonify({"message": "Voice assistant started."})
        else:
            return jsonify({"message": "Voice assistant is already active."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API endpoint to get recommendations
@app.route('/recommendations', methods=['GET'])
def recommendations_route():
    try:
        if not result_queue.empty():
            result = result_queue.get()
            if "error" in result:
                return jsonify({"error": result["error"]}), 500
            else:
                return jsonify(result)
        else:
            return jsonify({"message": "Voice assistant is still processing."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API endpoint to receive product data from frontend
@app.route('/receive_product_data', methods=['POST'])
def receive_product_data():
    global frontend_products_data
    print("Endpoint /receive_product_data was hit!")
    try:
        print("Request JSON:", request.json)
        product_data = request.json.get('products')
        if product_data:
            frontend_products_data = product_data
            print("\n--- Product Data Received from Frontend and Stored ---")
            print(f"Total products received: {len(product_data)}")
            for i, product in enumerate(product_data, 1):
                print(f"{i}. {product}")
            print("--- End of Product Data ---\n")
            return jsonify({"message": "Product data received and stored successfully.", "count": len(product_data)}), 200
        else:
            print("Warning: No products in the request")
            return jsonify({"error": "No product data received in the request."}), 400
    except Exception as e:
        print(f"Error in receive_product_data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Error receiving product data."}), 500

# Load data from the Excel file
# Load data from the Excel file (no changes needed)
def load_data():
    try:
        df = pd.read_excel('Price_Predict.xlsx')
        return df
    except Exception as e:
        raise Exception(f"Failed to load Excel file: {e}")

# Train model and predict price (no changes needed - keeping for reference)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
def predict_price(commodity):
    try:
        # Load data
        df = load_data()
        logger.info("Data loaded successfully.")

        # Convert Date to datetime
        df['Date'] = pd.to_datetime(df['Date'], format='%d-%m-%Y', errors='coerce')
        logger.info("Date converted to datetime.")

        # Drop rows with invalid dates
        df.dropna(subset=['Date'], inplace=True)
        logger.info("Dropped rows with invalid dates.")

        # Sort by Date
        df = df.sort_values(by='Date')
        logger.info("Data sorted by Date.")

        # Filter data for the given commodity
        df_filtered = df[df['Commodity'] == commodity]
        if df_filtered.empty:
            logger.warning(f"No data available for commodity: {commodity}")
            return {"error": f"No data available for {commodity}."}

        # Extract features and target
        df_filtered['Year'] = df_filtered['Date'].dt.year
        df_filtered['Month'] = df_filtered['Date'].dt.month
        df_filtered['Day'] = df_filtered['Date'].dt.day
        features = ['Year', 'Month', 'Day']
        target = 'Price (per unit)'
        X = df_filtered[features]
        y = df_filtered[target]

        # Train-test split
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        logger.info("Train-test split completed.")

        # Train model
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X_train, y_train)
        logger.info("Model trained successfully.")

        # Predict price for tomorrow
        tomorrow = datetime.today() + timedelta(days=1)
        input_data = pd.DataFrame([[tomorrow.year, tomorrow.month, tomorrow.day]],
                                  columns=['Year', 'Month', 'Day'])
        predicted_price = model.predict(input_data)[0]
        logger.info(f"Predicted price for {commodity}: {predicted_price}")

        # Prepare historical data
        historical_data = df_filtered[['Date', 'Price (per unit)']].tail(7)
        historical_data['Date'] = historical_data['Date'].dt.strftime('%Y-%m-%d')
        predicted_data = {
            "Date": tomorrow.strftime('%Y-%m-%d'),
            "Price (per unit)": predicted_price
        }
        historical_data = pd.concat([historical_data, pd.DataFrame([predicted_data])], ignore_index=True)

        return {
            "commodity": commodity,
            "predicted_price": predicted_price,
            "unit": df_filtered['Unit'].iloc[0],  # Use the unit from the dataset
            "historical_data": historical_data.to_dict(orient='records')
        }

    except Exception as e:
        logger.error(f"Error in predict_price: {e}")
        return {"error": f"Failed to predict price: {e}"}
    
# API endpoint to predict price (no changes needed - keeping for reference)
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

# Socket.IO event handlers
@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")
    emit('response', {'data': 'Connected to server'})

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")

@socketio.on('message')
def handle_message(data):
    print(f"Message from client: {data}")
    emit('response', {'data': f"Server received: {data}"}, broadcast=True)

# Default route for debugging
@app.route('/')
def home():
    return "Flask server is running!"

# Run the Flask app
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)