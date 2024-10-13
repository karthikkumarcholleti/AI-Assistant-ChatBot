import yfinance as yf
import spacy
from transformers import pipeline
import re
from datetime import datetime, timedelta

# Load spaCy NER model
nlp = spacy.load("en_core_web_sm")

# Load zero-shot classifier (BERT or Zero-Shot for intent detection)
classifier = pipeline('zero-shot-classification')
candidate_intents = ["price inquiry", "stock trend", "stock comparison", "stock price comparison", "stock news sentiment"]

# --- Time Period Detection Function ---
def detect_time_period_with_paraphrasing(user_query):
    user_query = user_query.lower()

    if "today" in user_query or "current" or "present" or "latest" in user_query:
        return '1d'
    elif re.search(r'\b(this|current)\s*week\b', user_query):
        return 'current week'
    elif re.search(r'\b(last|previous|past)\s*week\b', user_query):
        return 'last week'
    elif re.search(r'\bpast\s*5\s*days\b', user_query):
        return '5d'
    elif re.search(r'\b(last|past|previous)\s*month\b', user_query):
        return '1mo'
    elif re.search(r'\b(last|past|previous)\s*3\s*months\b', user_query):
        return '3mo'
    elif re.search(r'\b(last|past|previous)\s*6\s*months\b', user_query):
        return '6mo'
    elif re.search(r'\b(last|past|previous)\s*year\b', user_query):
        return '1y'
    elif re.search(r'\bthis\s*year\b', user_query):
        return 'ytd'
    return '1d'  # Default to 1 day if no match is found

# --- Stock Symbol Extraction using NER and fallback to yfinance ---
def get_stock_symbol(company_name):
    # Manual overrides for well-known companies
    manual_overrides = {
        "apple": "AAPL", "tesla": "TSLA", "microsoft": "MSFT", "amazon": "AMZN",
        "google": "GOOGL", "facebook": "META", "nvidia": "NVDA"
    }
    company_name = company_name.lower()
    
    # Check manual overrides first
    if company_name in manual_overrides:
        return manual_overrides[company_name]
    
    # Try to fallback to yfinance to get the symbol if manual overrides fail
    try:
        stock = yf.Ticker(company_name)
        return stock.ticker.upper() if stock.ticker else None
    except:
        return None

# --- Stock Symbol Extraction using NER ---
def extract_stock_symbols_using_ner(user_query):
    doc = nlp(user_query)

    # Extract organizations (ORG) detected by spaCy
    organizations = [ent.text for ent in doc.ents if ent.label_ == "ORG"]

    stock_symbols = []
    for org in organizations:
        # Search for stock symbol using manual overrides or Alpha Vantage (if included)
        symbol = get_stock_symbol(org)
        if symbol:
            stock_symbols.append(symbol)
        else:
            print(f"Sorry, I couldn't retrieve a stock symbol for {org}.")
    
    return stock_symbols if stock_symbols else None


# --- Intent Classification ---
def classify_intent(user_query):
    user_query = user_query.lower()

    if "price" in user_query or "current price" in user_query:
        return "price inquiry"
    elif "trend" in user_query or "how has" in user_query:
        return "stock trend"
    elif "compare" in user_query:
        return "stock comparison"
    elif "news" in user_query or "sentiment" in user_query:
        return "news sentiment"
    else:
        return "unknown"

# --- Price Inquiry Handler ---
# --- Update handle_price_inquiry to better handle synonyms ---
def handle_price_inquiry(stock_symbols, user_query):
    try:
        period = detect_time_period_with_paraphrasing(user_query)
        response = ""

        for stock_symbol in stock_symbols:
            stock_data = yf.Ticker(stock_symbol).history(period=period)
            if stock_data.empty:
                response += f"Sorry, I couldn't retrieve data for {stock_symbol}.\n"
            else:
                # Handle specific price types
                if "current" in user_query or "close" in user_query or "present" in user_query or "latest" in user_query:
                    current_price = stock_data['Close'].values[-1]
                    response += f"The close price of {stock_symbol.upper()} for {period} is {current_price:.2f}.\n"
                elif "open" in user_query:
                    open_price = stock_data['Open'].values[-1]
                    response += f"The open price of {stock_symbol.upper()} for {period} is {open_price:.2f}.\n"
                elif "high" in user_query:
                    high_price = stock_data['High'].values[-1]
                    response += f"The high price of {stock_symbol.upper()} for {period} is {high_price:.2f}.\n"
                elif "low" in user_query:
                    low_price = stock_data['Low'].values[-1]
                    response += f"The low price of {stock_symbol.upper()} for {period} is {low_price:.2f}.\n"
                elif "adj close" in user_query:
                    adj_close_price = stock_data['Adj Close'].values[-1]
                    response += f"The adjusted close price of {stock_symbol.upper()} for {period} is {adj_close_price:.2f}.\n"
                else:
                    response += "Sorry, I couldn't understand the specific price type you're asking for.\n"
        return response
    except Exception as e:
        return f"Error fetching stock data: {str(e)}"
    

# --- Stock Trend Handler ---
def handle_stock_trend(stock_symbol, user_query):
    try:
        period = detect_time_period_with_paraphrasing(user_query)

        if period == 'last week':
            start_date = (datetime.now() - timedelta(weeks=1)).strftime('%Y-%m-%d')
            end_date = datetime.now().strftime('%Y-%m-%d')
            stock_data = yf.Ticker(stock_symbol).history(start=start_date, end=end_date)
        elif period == 'current week':
            start_date = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime('%Y-%m-%d')
            end_date = datetime.now().strftime('%Y-%m-%d')
            stock_data = yf.Ticker(stock_symbol).history(start=start_date, end=end_date)
        else:
            stock_data = yf.Ticker(stock_symbol).history(period=period)
        
        if not stock_data.empty:
            first_price = stock_data['Close'].values[0]
            last_price = stock_data['Close'].values[-1]
            trend_direction = "upward" if last_price > first_price else "downward" if last_price < first_price else "sideways"
            return f"{stock_symbol.upper()} is trending {trend_direction} over the last {period}."
        else:
            return f"Sorry, I couldn't retrieve trend data for {stock_symbol}."
    except Exception as e:
        return f"Error fetching stock trend data: {str(e)}"

# --- Stock Comparison Handler ---
def handle_stock_comparison(stock_symbols, user_query):
    try:
        comparison_results = []
        period = detect_time_period_with_paraphrasing(user_query)

        for stock_symbol in stock_symbols:
            stock_data = yf.Ticker(stock_symbol).history(period=period)
            if stock_data.empty:
                comparison_results.append(f"Sorry, I couldn't retrieve data for {stock_symbol}.")
                continue

            if "current" in user_query or "close" in user_query:
                price = stock_data['Close'].values[-1]
                comparison_results.append(f"{stock_symbol.upper()}: {price:.2f}")
            elif "open" in user_query:
                price = stock_data['Open'].values[-1]
                comparison_results.append(f"{stock_symbol.upper()}: {price:.2f}")
            elif "high" in user_query:
                price = stock_data['High'].values[-1]
                comparison_results.append(f"{stock_symbol.upper()}: {price:.2f}")
            elif "low" in user_query:
                price = stock_data['Low'].values[-1]
                comparison_results.append(f"{stock_symbol.upper()}: {price:.2f}")
            else:
                return "Sorry, I couldn't understand which price to compare."

        return "Comparison of prices:\n" + "\n".join(comparison_results)
    except Exception as e:
        return f"Error fetching stock comparison data: {str(e)}"

# --- User Query Handler ---
def handle_user_query(user_query):
    stock_symbols = extract_stock_symbols_using_ner(user_query)
    print(f"Extracted stock symbols: {stock_symbols}")

    intent = classify_intent(user_query)
    print(f"Intent: {intent}")

    if intent == "price inquiry":
        return handle_price_inquiry(stock_symbols, user_query)
    elif intent == "stock trend":
        return handle_stock_trend(stock_symbols[0], user_query)
    elif intent == "stock comparison":
        return handle_stock_comparison(stock_symbols, user_query)
    else:
        return "Sorry, I don't understand the request."

# --- Testing the model ---
user_query = "What is the lowest price of Tesla and Microsoft?"
response = handle_user_query(user_query)
print(response) # 1d

user_query = "What is the lowest price of Tesla and Microsoft today?"
response = handle_user_query(user_query)
print(response) # 1d

user_query = "What is the peak price of Tesla and Microsoft today?"
response = handle_user_query(user_query)
print(response)    # SORRY, i
user_query = "What is the high price of Tesla and Microsoft?"
response = handle_user_query(user_query)
print(response) # shows 1mo

user_query = "Compare the high prices of Tesla and Microsoft this year.?"
response = handle_user_query(user_query)
print(response) #ytd

user_query = "Compare the high prices of Tesla and Microsoft last year.?"
response = handle_user_query(user_query)
print(response) #1y

user_query = "Compare the high prices of Microsoft and Apple last year.?"
response = handle_user_query(user_query)
print(response) #1y



# Tesla's current price
user_query = "What is the current price of Tesla?"
response = handle_user_query(user_query)
print(response)  # Error fetching stock data: 'NoneType' object is not iterable

user_query = "What is the current price of Microsoft?"
response = handle_user_query(user_query)
print(response)#1d

user_query = "What is the current price of Nvidia?"
response = handle_user_query(user_query)
print(response)#Error fetching stock data: 'NoneType' object is not iterable

user_query = "What is the current price of META?"
response = handle_user_query(user_query)
print(response)#1d

user_query = "What is the present price of Microsoft?"
response = handle_user_query(user_query)
print(response)  #Sorry, I couldn't understand the specific price type you're asking for.

#  Microsoft's high price today
user_query = "What is the high price of Microsoft today?"
response = handle_user_query(user_query)
print(response) #1d 

# Test price inquiry for Apple's low price last month
user_query = "What is the lowest price of Apple in the last month?"
response = handle_user_query(user_query)
print(response)  #1mo

#Stock Trend Inquiry Test
#not working for google & tesla
#not working for apple, but working for Apple
# Test stock trend for Tesla in the last 3 months
user_query = "How has Tesla been trending over the last 3 months?"
response = handle_user_query(user_query)
print(response)  #TypeError: 'NoneType' object is not subscriptable

user_query = "How has Apple been trending over the last 3 months?"
response = handle_user_query(user_query)
print(response)  #


user_query = "How has Microsoft been trending over the last 3 months?"
response = handle_user_query(user_query)
print(response) #

# Test stock trend for Amazon in the past week
user_query = "What is the stock trend for Apple in the last week?"
response = handle_user_query(user_query)
print(response)  # 

user_query = "What is the stock trend for Apple today?"
response = handle_user_query(user_query)
print(response)  # 

user_query = "What is the  trend for Apple in the last week?"
response = handle_user_query(user_query)
print(response)  # 


user_query = "How has Facebook been trending over the last 3 months?"
response = handle_user_query(user_query)
print(response) #TypeError: 'NoneType' object is not subscriptable

user_query = "How has Google been trending over the last 3 months?"
response = handle_user_query(user_query)
print(response) #TypeError: 'NoneType' object is not subscriptable

user_query = "How has Amazon been trending over the last 3 months?"
response = handle_user_query(user_query)
print(response) #working for amazon


#Stock Comparison Test

# Test comparing current prices of Tesla and Apple
user_query = "Compare today's current prices of Tesla and Apple."
response = handle_user_query(user_query)
print(response)  #1d

# Test comparing high prices of Tesla and Microsoft this year
user_query = "Compare the highest prices of Tesla and Microsoft this year."
response = handle_user_query(user_query)
print(response)  # ytd


user_query = "Compare the lowest prices of Tesla and Microsoft this year."
response = handle_user_query(user_query)
print(response) #ytd

user_query = "Compare the highest prices of Tesla and Apple this year."
response = handle_user_query(user_query)
print(response) #ytd

user_query = "Compare the highest prices of Microsoft and Apple last year."
response = handle_user_query(user_query)
print(response) #1y

user_query = "Compare the highest prices of Amazon and Microsoft this month."
response = handle_user_query(user_query)
print(response) #1mo




# Intent Testing
# Price inquiry intent
user_query = "What is the price of Tesla stock?"
response = classify_intent(user_query)
print(f"Intent: {response}")  # Should classify as "price inquiry"

# Stock trend intent
user_query = "How has Microsoft been trending over the last year?"
response = classify_intent(user_query)
print(f"Intent: {response}")  # Should classify as "stock trend"

# Stock comparison intent
user_query = "Compare Tesla and Amazon stock prices."
response = classify_intent(user_query)
print(f"Intent: {response}")  # showing price inquiry


#Error Handling
# Test with an invalid stock symbol
user_query = "What is the price of an unknown stock XYZ?"
response = handle_user_query(user_query)
print(response)  # Should return an error message saying the stock symbol couldn't be retrieved
