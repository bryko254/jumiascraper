from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from typing import List
import os
from dotenv import load_dotenv
from models import Base, Product

load_dotenv()

# Database connection
DATABASE_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@postgres:5432/jumia_db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Jumia Scraper API")

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
async def root():
    return {"message": "Welcome to Jumia Scraper API"}

@app.get("/health")
async def health_check():
    try:
        # Test database connection using text()
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            result.scalar()
        return {
            "status": "healthy", 
            "database": "connected",
            "message": "API is functioning normally"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/products/", response_model=List[dict])
def read_products(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    products = db.query(Product).offset(skip).limit(limit).all()
    return [{"id": p.id, 
             "name": p.name, 
             "price": p.price, 
             "image_url": p.image_url, 
             "product_url": p.product_url, 
             "category": p.category} for p in products]

@app.get("/products/{product_id}")
def read_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
