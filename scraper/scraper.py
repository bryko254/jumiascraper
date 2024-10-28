import os
import time
import json
import requests
from bs4 import BeautifulSoup
import pika
import redis
from dotenv import load_dotenv
import random
import logging
from urllib.parse import urlencode

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

load_dotenv()

def connect_to_rabbitmq():
    logging.info("Attempting to connect to RabbitMQ...")
    try:
        credentials = pika.PlainCredentials(
            os.getenv('RABBITMQ_USER', 'guest'),
            os.getenv('RABBITMQ_PASSWORD', 'guest')
        )
        parameters = pika.ConnectionParameters(
            host='rabbitmq',
            credentials=credentials
        )
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        channel.queue_declare(queue='product_queue', durable=True)
        logging.info("Successfully connected to RabbitMQ")
        return connection, channel
    except Exception as e:
        logging.error(f"Failed to connect to RabbitMQ: {str(e)}")
        raise

def connect_to_redis():
    logging.info("Attempting to connect to Redis...")
    try:
        redis_client = redis.Redis(host='redis', port=6379, db=0)
        redis_client.ping()
        logging.info("Successfully connected to Redis")
        return redis_client
    except Exception as e:
        logging.error(f"Failed to connect to Redis: {str(e)}")
        raise

def get_headers():
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36'
    ]
    return {
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }

CATEGORIES = {
    'Phones & Tablets': 'phones-tablets'
}

def get_page_count(soup):
    try:
        # Look for pagination div with class pg-w
        pagination = soup.select_one('div.pg-w')
        if pagination:
            # Get all pagination links (both spans and a tags)
            page_elements = pagination.select('span.pg, a.pg')
            
            # Initialize max page
            max_page = 1
            
            for element in page_elements:
                # Check if it's a link to "Last Page"
                if element.name == 'a' and 'Last Page' in element.get('aria-label', ''):
                    # Extract page number from href
                    href = element.get('href', '')
                    if 'page=' in href:
                        try:
                            page_num = int(href.split('page=')[1].split('#')[0])
                            max_page = max(max_page, page_num)
                        except (ValueError, IndexError):
                            continue
                
                # Also check numeric pages
                try:
                    if element.text.strip().isdigit():
                        page_num = int(element.text.strip())
                        max_page = max(max_page, page_num)
                except (ValueError, AttributeError):
                    continue
            
            logging.info(f"Found {max_page} total pages")
            return max_page
        
        logging.warning("No pagination found")
        return 1
        
    except Exception as e:
        logging.error(f"Error getting page count: {str(e)}")
        return 1

def scrape_product(url):
    logging.info(f"Starting to scrape URL: {url}")
    all_products = []
    
    try:
        # Get first page
        response = requests.get(url, headers=get_headers(), timeout=15)
        response.raise_for_status()
        
        logging.info(f"Response status: {response.status_code}")
        soup = BeautifulSoup(response.content, 'html.parser')

        # Get total pages
        total_pages = get_page_count(soup)
        logging.info(f"Found {total_pages} pages to scrape")

        # Process each page
        for page in range(1, total_pages + 1):
            try:
                if page > 1:
                    # Construct page URL
                    page_url = f"{url}?page={page}#catalog-listing"
                    logging.info(f"Scraping page {page}: {page_url}")
                    
                    # Add delay between pages
                    time.sleep(random.uniform(3, 7))
                    
                    response = requests.get(page_url, headers=get_headers(), timeout=15)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.content, 'html.parser')

                # Find all product articles on current page
                products = soup.select('article.prd')
                logging.info(f"Found {len(products)} products on page {page}")

                for product in products:
                    try:
                        # Extract product name
                        name_elem = product.select_one('h3.name')
                        if not name_elem:
                            continue
                        name = name_elem.text.strip()

                        # Extract price
                        price_elem = product.select_one('.prc')
                        if not price_elem:
                            continue
                        price_text = price_elem.text.strip()
                        price = float(price_text.replace('KSh', '').replace(',', '').strip())

                        # Extract old price
                        old_price_elem = product.select_one('.old')
                        old_price = None
                        if old_price_elem:
                            old_price_text = old_price_elem.text.strip()
                            old_price = float(old_price_text.replace('KSh', '').replace(',', '').strip())

                        # Extract discount
                        discount_elem = product.select_one('div._dsct')
                        discount = discount_elem.text.strip() if discount_elem else None

                        # Extract image URL
                        image_elem = product.select_one('img.img')
                        image_url = image_elem.get('data-src', '') if image_elem else ''

                        # Extract product URL
                        link_elem = product.select_one('a.core')
                        if not link_elem:
                            continue
                        product_url = f"https://www.jumia.co.ke{link_elem['href']}"

                        # Extract category
                        category = next(
                            (name for name, path in CATEGORIES.items() 
                             if path in url),
                            'Unknown'
                        )

                        product_data = {
                            'name': name,
                            'price': price,
                            'old_price': old_price,
                            'discount': discount,
                            'image_url': image_url,
                            'product_url': product_url,
                            'category': category
                        }
                        
                        all_products.append(product_data)
                        logging.info(f"Successfully scraped product: {name}")

                    except Exception as e:
                        logging.error(f"Error processing individual product: {str(e)}")
                        continue

            except Exception as e:
                logging.error(f"Error scraping page {page}: {str(e)}")
                continue
                
            # Add delay before next page
            if page < total_pages:
                time.sleep(random.uniform(3, 7))

        return all_products

    except Exception as e:
        logging.error(f"Error in scrape_product: {str(e)}")
        return None

def main():
    logging.info("Starting scraper service...")
    
    try:
        redis_client = connect_to_redis()
        connection, channel = connect_to_rabbitmq()
        
        logging.info(f"Will scrape categories: {list(CATEGORIES.keys())}")
        
        while True:
            for category_name, category_path in CATEGORIES.items():
                url = f"https://www.jumia.co.ke/{category_path}/"
                
                if not redis_client.get(url):
                    logging.info(f"Starting to scrape category: {category_name}")
                    products = scrape_product(url)
                    
                    # In scraper.py's main function
                    if products:
                        for product in products:
                            try:
                                message = json.dumps(product)
                                logging.info(f"Sending message for product: {product['name']}")
                                logging.info(f"Message content: {message[:200]}...")
                                
                                # Use publisher confirms
                                channel.confirm_delivery()
                                
                                channel.basic_publish(
                                    exchange='',
                                    routing_key='product_queue',
                                    body=message,
                                    properties=pika.BasicProperties(
                                        delivery_mode=2,  # make message persistent
                                        content_type='application/json'
                                    )
                                )
                                
                                logging.info(f"Message sent successfully: {product['name']}")
                            except Exception as e:
                                logging.error(f"Failed to send message: {str(e)}")
                        
                        redis_client.setex(url, 3600, 'scraped')
                        logging.info(f"Completed processing category: {category_name}")
                    else:
                        logging.warning(f"No products found for category: {category_name}")
                    
                    time.sleep(random.uniform(8, 12))
                else:
                    logging.info(f"Category {category_name} was recently scraped, skipping")
            
            logging.info("Completed scraping cycle. Waiting before next cycle...")
            time.sleep(300)
            
    except KeyboardInterrupt:
        logging.info("Scraping stopped by user")
    except Exception as e:
        logging.error(f"Unexpected error in main loop: {str(e)}")
    finally:
        if 'connection' in locals():
            connection.close()
            logging.info("Closed RabbitMQ connection")

if __name__ == "__main__":
    logging.info("Scraper initialization...")
    time.sleep(10)
    main()
