import os
import sys
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from dateutil.parser import parse
from datetime import datetime
import re

# Get the absolute path of the project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# Add the project root to the Python path
sys.path.insert(0, project_root)

# Now try to import
from src.logger import setup_logger

logger = setup_logger()

def get_mongodb_connection():
    load_dotenv()
    uri = os.getenv('MONGODB_URI')

    client = MongoClient(uri, server_api=ServerApi('1'))

    try:
        client.admin.command('ping')
        logger.info("Successfully connected to MongoDB")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise

    return client

def ensure_indices(db):
    students_collection = db["students"]
    students_collection.create_index("student_id", unique=True)
    students_collection.create_index([("test_results.date", -1)])
    
    tests_collection = db["tests"]
    tests_collection.create_index("test_id", unique=True)
    tests_collection.create_index("date")
    
    # Add more indices as needed

def get_database(db_name="students", create_indices=False):
    client = get_mongodb_connection()
    db = client[db_name]
    if create_indices:
        ensure_indices(db)
    return db


def build_query(teacher=None, class_name=None, start_date=None, end_date=None, **additional_filters):
    query = {}
    
    if teacher:
        query['teacher'] = teacher.strip()
    
    if class_name:
        query['class'] = class_name
    
    if start_date or end_date:
        query['test_results'] = query.get('test_results', {})
        query['test_results']['$elemMatch'] = {}
        if start_date:
            query['test_results']['$elemMatch']['date'] = {
                '$gte': datetime.strptime(start_date, '%Y-%m-%d') if isinstance(start_date, str) else start_date
            }
        if end_date:
            query['test_results']['$elemMatch']['date'] = query['test_results']['$elemMatch'].get('date', {})
            query['test_results']['$elemMatch']['date']['$lte'] = datetime.strptime(end_date, '%Y-%m-%d') if isinstance(end_date, str) else end_date
    
    query.update(additional_filters)
    
    return query
    

def parse_date(date_str):
    if not date_str:
        return None
    try:
        date = parse(date_str, fuzzy=True)
        if len(date_str) == 4 and date_str.isdigit():
            # If only a year is provided
            return datetime(int(date_str), 1, 1)
        return date
    except ValueError:
        print(f"Invalid date format: {date_str}")
        return None