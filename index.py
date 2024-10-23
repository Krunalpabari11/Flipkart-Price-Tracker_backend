from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
from bson import json_util
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager
import re
import time

app = Flask(__name__)
CORS(app)

# MongoDB connection
client = MongoClient('mongodb+srv://krunalpabari11:jghhPRrUoOickS49@cluster0.blsuc.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')
db = client['price_tracker']
products_collection = db['products']
price_history_collection = db['price_history']

# Helper function to scrape Flipkart product using Selenium
def scrape_flipkart_product(url):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Run in headless mode
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
    driver.get(url)

    # Wait for the page to load
    # time.sleep(5)

    # Get page source and parse with BeautifulSoup
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    # print(soup.prettify())
    driver.quit()

    title = soup.find('span', {'class': 'VU-ZEz'})
    price = soup.find('div', {'class': 'Nx9bqj CxhGGd'})

    description = soup.find('div', {'class': 'yN+eNk w9jEaj'})
    reviews = soup.find('div', {'class': 'XQDdHH'})


    # Clean and format data
    title = title.text.strip() if title else "N/A"
    price = float(re.sub(r'[^\d.]', '', price.text)) if price else 0.0
    description = description.text.strip() if description else "N/A"
    reviews_text = reviews.text if reviews else "0 reviews"

    return {
        'title': title,
        'price': price,
        'description': description,
        'ratings': reviews_text

    }

# Routes
@app.route('/api/products', methods=['GET'])
def get_products():
    search = request.args.get('search', '')
    min_price_str = request.args.get('min_price', '')
    max_price_str = request.args.get('max_price', '')

    if min_price_str == '' or min_price_str == '0':
        min_price = 0.0
    else:
        min_price = float(min_price_str)

    if max_price_str == '' or max_price_str == '0':
        max_price = float('inf')
    else:
        max_price = float(max_price_str)
    
    query = {}
    if search:
        query['title'] = {'$regex': search, '$options': 'i'}
    
    products = list(products_collection.find(query))
    
    result = []
    for product in products:
        price_history = list(price_history_collection.find({'product_id': product['_id']}).sort('checked_at', -1))
        
        if not price_history:
            continue
            
        latest_price = price_history[0]['price']
        
        if min_price <= latest_price <= max_price:
            result.append({
                'id': str(product['_id']),
                'title': product['title'],
                'description': product['description'],
                'url': product['url'],
                'ratings': product['ratings'],
                'current_price': latest_price,
                'price_history': [{
                    'price': ph['price'],
                    'checked_at': ph['checked_at'].isoformat()
                } for ph in price_history]
            })
    
    return jsonify(result)

@app.route('/api/products', methods=['POST'])
def add_product():
    url = request.json.get('url')

    if not url:
        return jsonify({'error': 'URL is required'}),   400
    
    pro = products_collection.find_one({'url': url})
    if pro:
        return jsonify({'error': 'Product already exists'}), 400
    product_details = scrape_flipkart_product(url)
    if not product_details:
        return jsonify({'error': 'Failed to scrape product details'}), 400

    product = {
        'title': product_details['title'],
        'description': product_details['description'],
        'url': url,
        'ratings': product_details['ratings'],
        'created_at': datetime.utcnow()
    }
    
    result = products_collection.insert_one(product)
    product_id = result.inserted_id
    
    price_history = {
        'product_id': product_id,
        'price': product_details['price'],
        'checked_at': datetime.utcnow()
    }
    price_history_collection.insert_one(price_history)
    print("it is here")
    return jsonify({
        'id': str(product_id),
        'title': product['title'],
        'description': product['description'],
        'url': product['url'],
        'ratings': product['ratings'],
        'current_price': price_history['price'],
        'price_history':[{
            'price': price_history['price'],
            'checked_at': price_history['checked_at'].isoformat()
        }] 
    })

@app.route('/api/products/recheck', methods=['POST'])
def recheck_price():
    url=request.json.get('url') 
    if not url:
        return jsonify({'error': 'URL is required'}), 400   
    product_details = scrape_flipkart_product(url)

    more_details=products_collection.find_one({'url': url})

    
    if not product_details:
        return jsonify({'error': 'Failed to scrape product details'}), 400
    
    price_history = {
        'product_id': more_details['_id'],
        'price': product_details['price'],
        'checked_at': datetime.utcnow()
    }
    price_history_collection.insert_one(price_history)
    
    return jsonify({
        'price': price_history['price'],
        'checked_at': price_history['checked_at'].isoformat()
    })

@app.route('/api/getAllProducts', methods=['GET'])
def getAllProducts():
    products = list(products_collection.find({}))
    return json_util.dumps(products)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
