import pandas as pd
from src.components.db_connection import get_database, build_query, logger
from src.pipelines import mongo_db_pipelines as m_db
from dotenv import load_dotenv
import os
import time
from faker import Faker
import random
import hashlib
from dotenv import load_dotenv

load_dotenv()

def get_default_query():
    return build_query(teacher=os.getenv('TEACHER2'))

fake = Faker()

# Global variables to store the data and timestamp
_data = None
_last_load_time = 0
_cache_duration = 3600  # Cache duration in seconds (e.g., 1 hour)

def fake_test_id():
    """Generate a fake test ID."""
    class_names = ['Biology', 'Chemistry', 'Anatomy']
    test_names = ['Midterm', 'Final', 'Quiz', 'Project', 'Exam']
    
    class_name = random.choice(class_names)
    test_name = random.choice(test_names)
    fake_date = fake.date_between(start_date='-1y', end_date='today').strftime('%Y%m%d')
    
    return f"{class_name}_{test_name}_{fake_date}"

def create_mapping(original_values, fake_function):
    """Create a mapping for anonymization."""
    return {value: fake_function() for value in set(original_values)}

def anonymize_df(df):
    """Anonymize the dataframe by replacing identifiable information."""
    logger.info("Starting dataframe anonymization")
    anon_df = df.copy()
    
    # Create mappings for names and IDs
    student_id_map = {id: hashlib.md5(str(id).encode()).hexdigest()[:8] for id in df['student_id'].unique()}
    first_name_map = {name: fake.first_name() for name in df['first_name'].unique()}
    last_name_map = {name: fake.last_name() for name in df['last_name'].unique()}
    class_name_map = {class_name: f"Fake-class{fake.numerify('####')}" for class_name in df['class_name'].unique()}
    
    # Create a mapping for test_ids to ensure consistency
    test_id_map = {}
    for test_id in df['test_id'].unique():
        parts = test_id.split('_')
        if len(parts) >= 3:
            new_test_id = f"{class_name_map.get(parts[0], parts[0])}_{fake.word().capitalize()}_{fake.date_this_year().strftime('%Y%m%d')}"
        else:
            new_test_id = f"Test_{fake.word().capitalize()}_{fake.date_this_year().strftime('%Y%m%d')}"
        test_id_map[test_id] = new_test_id
    
    # Apply mappings
    anon_df['student_id'] = anon_df['student_id'].map(student_id_map)
    anon_df['first_name'] = anon_df['first_name'].map(first_name_map)
    anon_df['last_name'] = anon_df['last_name'].map(last_name_map)
    anon_df['class_name'] = anon_df['class_name'].map(class_name_map)
    anon_df['test_id'] = anon_df['test_id'].map(test_id_map)
    
    # Update test_name based on the new test_id
    anon_df['test_name'] = anon_df['test_id'].apply(lambda x: ' '.join(x.split('_')[1:-1]))
    
    logger.info("Dataframe anonymization completed")
   
    return anon_df

def load_data(force_reload=False, anonymize=False):
    global _data, _last_load_time
    
    current_time = time.time()
    
    # If data is cached and not expired, return the cached data
    if not force_reload and _data is not None and (current_time - _last_load_time) < _cache_duration:
        logger.info("Returning cached data")
        return _data

    logger.info("Loading fresh data from database")
    
    load_dotenv()
    db = get_database(create_indices=True)
    students = db['students']
    teacher = os.getenv('TEACHER2')
    query = build_query(teacher=teacher)
    
    pipeline = m_db.comprehensive_test_analysis_pipeline(query)
    results = list(students.aggregate(pipeline))
    
    df = pd.DataFrame(results)
    
    if anonymize:
        logger.info("Anonymizing data")
        df = anonymize_df(df)
    
    # Store the loaded data and update the timestamp
    _data = df
    _last_load_time = current_time
    
    return _data

def get_data(anonymize=False):
    return load_data(anonymize=anonymize)