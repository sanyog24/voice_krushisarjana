import speech_recognition as sr
from gtts import gTTS
import os
import tempfile
import pygame
import google.generativeai as genai
from deep_translator import GoogleTranslator
import time
import nltk
from nltk.stem import WordNetLemmatizer


nltk.download('wordnet')
lemmatizer = WordNetLemmatizer()

# Configure Gemini API
genai.configure(api_key="AIzaSyDgKp1SeumB6e8ooanP5n35C5l45BR0KGg")
translator = GoogleTranslator()

# Sample product data
products = [
    {"category": "pesticide", "type": "organic", "name": "Neem Oil", "price": 500},
    {"category": "pesticide", "type": "non-organic", "name": "Glyphosate", "price": 300},
    {"category": "seed", "type": "organic", "name": "Organic Tomato Seeds", "price": 150},
    {"category": "seed", "type": "non-organic", "name": "Hybrid Maize Seeds", "price": 200},
]


# Function to play speech
def speak(text, lang):
    tts = gTTS(text, lang=lang, slow=False)
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as fp:
        temp_path = fp.name
        tts.save(temp_path)
    pygame.mixer.init()
    pygame.mixer.music.load(temp_path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        continue
    pygame.mixer.quit()
    time.sleep(1)
    os.remove(temp_path)


# Function to recognize speech
def recognize_speech(language):
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)
    try:
        text = recognizer.recognize_google(audio, language=language)  # Use selected language
        return text.lower()
    except sr.UnknownValueError:
        return "Sorry, I could not understand."
    except sr.RequestError:
        return "Request error from Google API."


# Get Gemini AI response
def get_gemini_response(prompt):
    model = genai.GenerativeModel("gemini-pro")
    response = model.generate_content(prompt)
    return response.text




nltk.download('wordnet')
lemmatizer = WordNetLemmatizer()

def extract_preferences(query, preferences):
    query = query.lower()
    words = [lemmatizer.lemmatize(word) for word in query.split()]  # Normalize words

    pesticide_words = ["pesticide", "pesticides", "कीटनाशक", "कीटकनाशक", "कीटनाशक दवा"]
    seed_words = ["seed", "seeds", "बीज", "बियाणे"]
    organic_words = ["organic", "jaivik", "जैविक", "सेंद्रिय"]
    non_organic_words = ["non-organic", "inorganic", "chemical", "रासायनिक", "अजैविक"]

    if any(word in pesticide_words for word in words):
        preferences["category"] = "pesticide"
    elif any(word in seed_words for word in words):
        preferences["category"] = "seed"

    if any(word in organic_words for word in words):
        preferences["type"] = "organic"
    elif any(word in non_organic_words for word in words):
        preferences["type"] = "non-organic"

    return preferences



# Recommend products based on preferences
def recommend_products(preferences):
    recommendations = [product for product in products if
                       product["category"] == preferences.get("category") and product["type"] == preferences.get(
                           "type")]
    return recommendations



def voice():
    selected_language = None
    preferences = {"category": None, "type": None}
    exit_keywords = ["exit", "quit", "बंद करो", "बंद करें", "बाहर जाएं", "बाहेर जा"]

    while True:
        if not selected_language:
            print("Hello Shetkari! Please choose a language: English, Hindi, Marathi")
            speak("Hello Shetkari! Please choose a language: English, Hindi, Marathi", "en")
            language = recognize_speech("en").lower()
            if any(word in language for word in exit_keywords):
                print("Exiting...")
                speak("Goodbye!", "en")
                break
            lang_code = {"english": "en", "hindi": "hi", "marathi": "mr"}.get(language, "en")
            selected_language = lang_code
            print(f"Selected Language: {language.capitalize()}")

        user_query = recognize_speech(selected_language)
        if any(word in user_query for word in exit_keywords):
            print("Exiting...")
            speak("Goodbye!", selected_language)
            break

        print(f"User: {user_query}")

        detected_lang = GoogleTranslator(source='auto', target=selected_language).translate(user_query)
        if detected_lang:
            user_query = detected_lang

        preferences = extract_preferences(user_query, preferences)

        if preferences["category"] and not preferences["type"]:
            speak(
                "कृपया प्रकार निर्दिष्ट करें। जैविक या अजैविक?" if selected_language == "hi" else "कृपया प्रकार निर्दिष्ट करा. सेंद्रिय किंवा अजैविक?" if selected_language == "mr" else "Please specify type: Organic or Non-organic?",
                selected_language)
            user_query = recognize_speech(selected_language)
            preferences = extract_preferences(user_query, preferences)
        elif preferences["type"] and not preferences["category"]:
            speak(
                "कृपया श्रेणी निर्दिष्ट करें। बीज या कीटनाशक?" if selected_language == "hi" else "कृपया श्रेणी निर्दिष्ट करा. बियाणे किंवा कीटकनाशक?" if selected_language == "mr" else "Please specify category: Seed or Pesticide?",
                selected_language)
            user_query = recognize_speech(selected_language)
            preferences = extract_preferences(user_query, preferences)
        elif not preferences["category"] and not preferences["type"]:
            speak(
                "कृपया श्रेणी और प्रकार दोनों निर्दिष्ट करें।" if selected_language == "hi" else "कृपया श्रेणी आणि प्रकार दोन्ही निर्दिष्ट करा." if selected_language == "mr" else "Please specify both category and type.",
                selected_language)
            continue

        recommendations = recommend_products(preferences)

        if recommendations:
            response = "मैं निम्नलिखित उत्पादों की सिफारिश करता हूँ:\n" if selected_language == "hi" else "मी खालील उत्पादने शिफारस करतो:\n" if selected_language == "mr" else "I recommend the following products:\n"
            response += "\n".join([
                                      f"{product['name']} के लिए {product['price']} रुपये" if selected_language == "hi" else f"{product['name']} साठी {product['price']} रुपये" if selected_language == "mr" else f"{product['name']} for {product['price']} rupees"
                                      for product in recommendations])
        else:
            response = "माफ करें, आपकी पसंद के लिए कोई उत्पाद नहीं मिला।" if selected_language == "hi" else "माफ करा, तुमच्या पसंतीसाठी कोणतेही उत्पादन आढळले नाही." if selected_language == "mr" else "Sorry, no products found for your preference."

        print(f"Assistant: {response}")
        speak(response, selected_language)


voice()