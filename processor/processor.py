# First import logging
import logging
# Then import everything else
import os
import time
import json
import pika
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from dotenv import load_dotenv
from datetime import datetime

# Configure logging immediately after import
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Load environment variables
load_dotenv()

# Database setup
DATABASE_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@postgres:5432/jumia_db"
engine = create_engine(DATABASE_URL)
Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Define models
class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    current_price = Column(Float)
    image_url = Column(String)
    product_url = Column(String)
    category = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    price_histories = relationship("PriceHistory", back_populates="product")

class PriceHistory(Base):
    __tablename__ = "price_histories"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    price = Column(Float)
    listed_price = Column(Float, nullable=True)
    discount = Column(String, nullable=True)
    recorded_at = Column(DateTime)
    product = relationship("Product", back_populates="price_histories")

# Create tables
Base.metadata.create_all(bind=engine)

def process_message(ch, method, properties, body):
    try:
        logging.info("================== NEW MESSAGE ===================")
        logging.info(f"Received message: {body[:200]}...")  # Show first 200 chars
        
        product_data = json.loads(body)
        logging.info(f"Decoded product data: {product_data}")
        
        db = SessionLocal()
        
        try:
            # Check database connection
            db.execute("SELECT 1")
            logging.info("Database connection successful")
            
            # Rest of the processing...
            new_product = Product(
                name=product_data['name'],
                current_price=product_data['price'],
                image_url=product_data['image_url'],
                product_url=product_data['product_url'],
                category=product_data['category'],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            logging.info(f"Created product object: {new_product.name}")
            db.add(new_product)
            logging.info("Added to session")
            
            db.flush()
            logging.info(f"Flushed to database with ID: {new_product.id}")
            
            # Create price history
            price_history = PriceHistory(
                product_id=new_product.id,
                price=product_data['price'],
                listed_price=product_data.get('old_price'),
                discount=product_data.get('discount'),
                recorded_at=datetime.utcnow()
            )
            
            db.add(price_history)
            logging.info("Added price history")
            
            db.commit()
            logging.info("Transaction committed")
            
            # Acknowledge the message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logging.info("Message acknowledged")
            
        except Exception as e:
            logging.error(f"Database error: {str(e)}")
            db.rollback()
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        finally:
            db.close()
            
    except Exception as e:
        logging.error(f"Processing error: {str(e)}")
        if not method.delivery_tag:
            logging.error("No delivery tag available")
        else:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def main():
    logging.info("Starting processor service...")
    
    while True:
        try:
            credentials = pika.PlainCredentials(
                os.getenv('RABBITMQ_USER', 'guest'),
                os.getenv('RABBITMQ_PASSWORD', 'guest')
            )
            parameters = pika.ConnectionParameters(
                host='rabbitmq',
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            
            logging.info("Connecting to RabbitMQ...")
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()
            
            # Declare queue with simple settings
            channel.queue_declare(
                queue='product_queue', 
                durable=True
            )
            channel.basic_qos(prefetch_count=1)
            
            logging.info("Starting to consume messages...")
            channel.basic_consume(
                queue='product_queue',
                on_message_callback=process_message,
                auto_ack=False  # Don't auto-acknowledge
            )
            
            logging.info("Ready to process messages")
            channel.start_consuming()
            
        except pika.exceptions.AMQPConnectionError as e:
            logging.error(f"AMQP Connection Error: {str(e)}")
            logging.info("Retrying in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            logging.error("Full error details: ", exc_info=True)
            logging.info("Retrying in 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    logging.info("Processor initialization...")
    time.sleep(10)  # Wait for RabbitMQ and PostgreSQL to be ready
    main()
