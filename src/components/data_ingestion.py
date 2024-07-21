
import pandas as pd
import numpy as np
import datetime
import re
import os
import sys
from dotenv import load_dotenv
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId
from pymongo.mongo_client import MongoClient

# Get the absolute path of the project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# Add the project root to the Python path
sys.path.insert(0, project_root)

from components.db_connection import get_database, logger


load_dotenv()
CSV_DIR = os.getenv('CSV_DIR')


def extract_test_info(file_path):
    """
    Extract test information from the file path and name.

    :param file_path: Full path to the CSV file
    :return: Dictionary containing test information
    """
    logger.info("Extracting test info")

    path_parts = file_path.split(os.sep)
    # Assumes class name is the parent directory name
    class_name = path_parts[-2]
    file_name = os.path.basename(file_path)

    match = re.match(r"(.+)_(\d+)_(\d+)_(\d+)\.csv$", file_name)
    if match:
        test_name, month, day, year = match.groups()
        test_date = datetime.datetime(int(year), int(month), int(day))
    else:
        test_name, test_date = file_name, datetime.datetime.now()

    # Unique id based on details of test
    test_id = f"{class_name}_{test_name}_{test_date.strftime('%Y%m%d')}"

    test_info = {
        "test_id": test_id,
        "class": class_name,
        "assessment_name": test_name,
        "date": test_date,
    }
    logger.info("Test info successfully extracted")

    return test_info


def process_csv(file_path):
    """
    Process the CSV file and extract necessary information.

    :param file_path: Path to the CSV file
    :return: DataFrame containing the processed data and assessment_points_possible
    """
    match = re.search(r"_(\d+)_(\d+)_(\d+)\.csv$", file_path)
    if match:
        month, day, year = match.groups()
        date = pd.to_datetime(f"{year}-{month}-{day}")
    else:
        date = pd.to_datetime('today')

    df = pd.read_csv(file_path, header=None)

    metadata_categories = df.iloc[:10, 10].tolist()
    metadata = df.iloc[:10, 11:].T
    metadata.columns = metadata_categories
    metadata.index = [f'Q{i}' for i in range(1, metadata.shape[0] + 1)]

    student_info = df.iloc[10:, :10].reset_index(drop=True)
    student_info.columns = df.iloc[9, :10]

    responses = df.iloc[10:, 11:].reset_index(drop=True)
    responses.columns = metadata.index

    question_columns = pd.MultiIndex.from_product(
        [metadata.index, ['response'] + metadata_categories])
    final_df = pd.DataFrame(index=student_info.index, columns=question_columns)

    for question in metadata.index:
        final_df.loc[:, (question, 'response')] = responses[question]
        for category in metadata_categories:
            final_df.loc[:, (question, category)
                         ] = metadata.loc[question, category]

    for col in student_info.columns:
        final_df[('student_info', col)] = student_info[col]
    final_df[('student_info', 'date_given')] = date

    assessment_points_possible = int(
        final_df[('student_info', 'assessment_points_possible')].iloc[0])
    final_df = final_df.sort_index(axis=1)

    return final_df, date, assessment_points_possible


def update_mongodb(df, test_info, db):
    """
    Update MongoDB with new test data, updating existing students and creating new ones as needed.

    :param df: The pandas DataFrame containing the test data
    :param test_info: A dictionary containing test-level information
    :param db: MongoDB database connection
    """
    students_collection = db["students"]
    tests_collection = db["tests"]

    test_document = {
        "_id": ObjectId(),
        "test_id": test_info['test_id'],
        "date": test_info['date'],
        "class": test_info['class'],
        "assessment_name": test_info['assessment_name'],
        "assessment_points_possible": test_info['assessment_points_possible'],
        "questions": [],
        "student_results": []
    }

    question_metadata_fields = [
        'item', 'standard', 'item_type_name', 'dok', 'passage_genre',
        'points', 'correct_answer', 'percent_correct'
    ]

    for question in df.columns.levels[0]:
        if question != 'student_info':
            question_data = {"question_id": question}
            for field in question_metadata_fields:
                if (question, field) in df.columns:
                    question_data[field] = df.loc[:, (question, field)].iloc[0]
            test_document['questions'].append(question_data)

    for _, row in df.iterrows():
        student_id = row[('student_info', 'student_id')]

        student_data = {
            "_id": ObjectId(),
            "student_id": student_id,
            "first_name": row[('student_info', 'first_name')],
            "last_name": row[('student_info', 'last_name')],
            "school": row[('student_info', 'school')],
            "teacher": row[('student_info', 'teacher')]
        }

        test_result = {
            "test_id": test_info['test_id'],
            "date": test_info['date'],
            "overall_score": row[('student_info', 'overall_score')],
            "overall_percentage": row[('student_info', 'overall_percentage')],
            "responses": []
        }

        for question in df.columns.levels[0]:
            if question != 'student_info':
                response = {
                    "question": question,
                    "response": row[(question, 'response')]
                }
                test_result['responses'].append(response)

        students_collection.update_one(
            {"student_id": student_id},
            {
                "$set": student_data,
                "$push": {"test_results": test_result}
            },
            upsert=True
        )


        test_document['student_results'].append({
            "student_id": student_id,
            "overall_score": test_result['overall_score'],
            "overall_percentage": test_result['overall_percentage']
        })
    logger.info(f"Updated/inserted student records for: {test_info['class']}")

    tests_collection.update_one(
    {"test_id": test_info['test_id']},
    {"$set": test_document},
    upsert=True 
    )

    logger.info(f"Inserted test document: {test_info['test_id']}")


def get_csv_files(directory):
    """
    Retrieve a list of CSV files from the given directory.

    :param directory: Directory to search for CSV files
    :return: List of CSV file paths
    """
    files = []
    for dirpath, _, filenames in os.walk(directory):
        for filename in filenames:
            if filename.endswith('.csv'):
                files.append(os.path.join(dirpath, filename))
    return files


def process_all_csv_files(directory):
    """
    Process all CSV files in the specified directory.

    :param directory: Directory containing CSV files
    :return: List of tuples containing DataFrame and test information
    """
    logger.info(f"Processing all CSV files in directory: {directory}")
    processed_data = []
    for file_path in get_csv_files(directory):
        test_info = extract_test_info(file_path)
        df, date, assessment_points_possible = process_csv(file_path)
        test_info['assessment_points_possible'] = assessment_points_possible
        test_info['date'] = date
        processed_data.append((df, test_info))
    logger.info(f"Processed {len(processed_data)} CSV files")
    return processed_data


def update_mongodb_with_processed_data(processed_data, db):
    """
    Update MongoDB with processed data.

    :param processed_data: List of tuples containing DataFrame and test information
    :param db: MongoDB database connection
    """
    for df, test_info in processed_data:
        update_mongodb(df, test_info, db)

def drop_collection(db, collection_name):
    if collection_name in db.list_collection_names():
        db.drop_collection(collection_name)
        print(f"Collection '{collection_name}' dropped.")
    else:
        print(f"Collection '{collection_name}' does not exist.")


def main():
    """
    Main function to process CSV files and update MongoDB.
    """
    
    logger.info("Starting data ingestion process")

    db = get_database()

    processed_data = process_all_csv_files(CSV_DIR)
    update_mongodb_with_processed_data(processed_data, db)

    logger.info("Data ingestion process completed")


if __name__ == "__main__":
    main()
