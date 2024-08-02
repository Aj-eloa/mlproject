import dash
from dash import html, dcc, dash_table, Input, Output, State, callback
import pandas as pd
import sys
import os
# Get the absolute path of the project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Add the project root to the Python path
sys.path.insert(0, project_root)

from src.components.db_connection import get_database, build_query, logger
from src.utils import identify_students_with_nan
from dotenv import load_dotenv
import random
import hashlib
from faker import Faker

fake = Faker()

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
    
    # Create mappings for each column
    student_id_mapping = create_mapping(df['student_id'], lambda: f"S-{fake.numerify('######')}")
    first_name_mapping = create_mapping(df['first_name'], fake.first_name)
    last_name_mapping = create_mapping(df['last_name'], fake.last_name)
    teacher_mapping = create_mapping(df['teacher'], fake.name)
    test_id_mapping = create_mapping(df['test_id'], fake_test_id)
    
    # Apply mappings
    anon_df['student_id'] = anon_df['student_id'].map(student_id_mapping)
    anon_df['first_name'] = anon_df['first_name'].map(first_name_mapping)
    anon_df['last_name'] = anon_df['last_name'].map(last_name_mapping)
    anon_df['teacher'] = anon_df['teacher'].map(teacher_mapping)
    anon_df['test_id'] = anon_df['test_id'].map(test_id_mapping)
    
    # Update class_name and test_name based on the new test_id
    anon_df['class_name'] = anon_df['test_id'].str.split('_').str[0]
    anon_df['test_name'] = anon_df['test_id'].str.split('_').str[1]
    
    logger.info("Dataframe anonymization completed")
    return anon_df

def load_data(anonymize=False):
    """Load and prepare data from the database."""
    logger.info("Starting data loading process")
    
    # Get the directory of the current script
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Construct the path to the .env file in the parent directory
    dotenv_path = os.path.join(os.path.dirname(current_dir), '.env')

    # Load the .env file
    load_dotenv(dotenv_path=dotenv_path)
    logger.info("Environment variables loaded")
    
    db = get_database(create_indices=True)
    logger.info("Connected to database")
    
    students = db['students']
    teacher = os.getenv('TEACHER2')
    logger.info(f"Teacher retrieved: {teacher}")
    
    query = build_query(teacher=teacher)
    logger.info(f"Query built: {query}")
    
    missed_test = identify_students_with_nan(students, 'overall_percentage', query=query)
    missed_test_df = pd.DataFrame(missed_test)
    logger.info(f"Missed test data retrieved: {len(missed_test_df)} records")
    
    if anonymize:
        logger.info("Anonymizing data")
        missed_test_df = anonymize_df(missed_test_df)
    
    # Extract class name and test name from test_id
    missed_test_df['class_name'] = missed_test_df['test_id'].str.split('_').str[0]
    missed_test_df['test_name'] = missed_test_df['test_id'].str.split('_').str[1:-1].str.join('_')
    
    # Group by student and count missed tests
    student_summary = missed_test_df.groupby(['student_id', 'first_name', 'last_name', 'teacher']).size().reset_index(name='missed_tests_count')
    
    logger.info("Data loading and processing completed")
    return missed_test_df, student_summary

def create_dash_layout(student_summary, width='100%', height='600px', highlight_color='#ADD8E6'):
    """Create the Dash app layout."""
    return html.Div([
        dcc.Input(id="search-input", type="text", placeholder="Search by name or teacher...", style={'width': '100%', 'marginBottom': '10px'}),
        dash_table.DataTable(
            id='student-table',
            columns=[{"name": i, "id": i} for i in student_summary.columns],
            data=student_summary.to_dict('records'),
            page_size=10,
            style_table={'height': height, 'overflowY': 'auto'},
            style_cell={'textAlign': 'left', 'font-family': 'Arial, sans-serif', 'padding': '5px'},
            style_header={'backgroundColor': 'lightgrey', 'fontWeight': 'bold'},
            style_data_conditional=[
                {'if': {'row_index': 'odd'}, 'backgroundColor': 'rgb(248, 248, 248)'},
                {'if': {'state': 'selected'}, 'backgroundColor': highlight_color, 'border': f'1px solid {highlight_color}'}
            ],
            sort_action="native",
            filter_action="native",
            page_action="native",
            page_current=0,
        ),
        html.Div(id='missed-tests-output', style={
            'marginTop': '20px',
            'padding': '10px',
            'backgroundColor': 'white',
            'border': '1px solid #ddd',
            'borderRadius': '5px'
        })
    ], style={'width': width})

def register_callbacks(app, student_summary, missed_test_df):
    """Register callbacks for the Dash app."""
    @app.callback(
        Output('student-table', 'data'),
        Input('search-input', 'value')
    )
    def update_table(search_value):
        if search_value:
            filtered_df = student_summary[
                student_summary['first_name'].str.contains(search_value, case=False) |
                student_summary['last_name'].str.contains(search_value, case=False) |
                student_summary['teacher'].str.contains(search_value, case=False)
            ]
        else:
            filtered_df = student_summary
        return filtered_df.to_dict('records')

    @app.callback(
        Output('missed-tests-output', 'children'),
        Input('student-table', 'active_cell'),
        Input('student-table', 'page_current'),
        Input('student-table', 'page_size'),
        State('student-table', 'data')
    )
    def display_missed_tests(active_cell, page_current, page_size, data):
        if active_cell:
            row_index = page_current * page_size + active_cell['row']
            if row_index < len(data):
                row = data[row_index]
                student_id = row['student_id']
                student_tests = missed_test_df[missed_test_df['student_id'] == student_id]
                
                date_column = 'test_dates' if 'test_dates' in student_tests.columns else 'date'
                formatted_dates = pd.to_datetime(student_tests[date_column]).dt.strftime('%Y-%m-%d')
                
                return html.Div([
                    html.H4([
                        f"{row['first_name']} {row['last_name']} ",
                        html.Span(f"(Teacher: {row['teacher']}, Class: {student_tests['class_name'].iloc[0]})", 
                                  style={'fontSize': '1em', 'fontWeight': 'normal'})
                    ], style={'color': 'black'}),
                    html.Ul([
                        html.Li([
                            html.Em(f"{test_name}"), 
                            f" on {date}"
                        ], style={'color': 'black'}) 
                        for test_name, date in zip(student_tests['test_name'], formatted_dates)
                    ])
                ])
        return html.Div("Click on a student to see their missed tests.", style={'color': 'black'})

def create_interactive_table_dash_app(anonymize=False, width='80%', height='400px', highlight_color='#FAD1BB'):
    """Create and return the Dash app for the interactive student table."""
    logger.info("Creating interactive student table")
    missed_test_df, student_summary = load_data(anonymize)
    
    app = dash.Dash(__name__)
    app.layout = create_dash_layout(student_summary, width, height, highlight_color)
    register_callbacks(app, student_summary, missed_test_df)
    
    logger.info("Interactive student table created successfully")
    return app

if __name__ == "__main__":
    logger.info("Starting standalone app")
    app = create_interactive_table_dash_app(anonymize=True)
    logger.info("Running server")
    app.run_server(debug=True, port=8051)