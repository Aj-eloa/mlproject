import os
import pandas as pd
from src.components.db_connection import get_database, build_query, logger
from src.pipelines import mongo_db_pipelines as m_db
from dotenv import load_dotenv

load_dotenv()


def get_anonymized_data():
    """Load pre-anonymized data from CSV file."""
    logger.info("Loading pre-anonymized data")
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'fake_data.csv')
    
    if os.path.exists(csv_path):
        return pd.read_csv(csv_path)
    else:
        logger.error("Pre-anonymized CSV not found. Unable to load anonymized data.")
        raise FileNotFoundError("fake_data.csv not found")

def load_real_data():
    """Load real data from the database."""
    logger.info("Loading real data from database")
    
    db = get_database(create_indices=True)
    students = db['students']
    teacher = os.getenv('TEACHER2')
    query = build_query(teacher=teacher)
    
    pipeline = m_db.comprehensive_test_analysis_pipeline(query)
    results = list(students.aggregate(pipeline))
    
    return pd.DataFrame(results)

def get_data(anonymize=False):
    """
    Get data based on the anonymize flag.
    If anonymize is True, return pre-anonymized data from CSV.
    If anonymize is False, return real data from the database.
    """
    if anonymize:
        return get_anonymized_data()
    else:
        return load_real_data()


get_anonymized_data()