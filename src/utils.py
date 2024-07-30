from dash import Dash, html, dcc, dash_table, Input, Output, callback, State
from IPython.display import display
import dash_bootstrap_components as dbc
from bson.son import SON
import pandas as pd
import dash
from dash.dependencies import Input, Output
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from src.components.db_connection import build_query
from pymongo.collection import Collection



def describe_numeric_field_pandas(data, field, query):
    if isinstance(data, Collection):
        # If data is a MongoDB collection, use aggregation pipeline

        pipeline = []

        if query:
            pipeline.append({'$match': query})

        pipeline.extend([
            {"$unwind": "$test_results"},
            {"$project": {
                "value": f"$test_results.{field}"
            }}
        ]) 
        cursor = data.aggregate(pipeline)
        series = pd.Series([doc['value'] for doc in cursor])
    else:
        # If data is a list of dictionaries (pre-filtered data)
        series = pd.Series([test[field] for doc in data for test in doc.get('test_results', [])])

    # Convert to numeric, coercing errors to NaN
    series = pd.to_numeric(series, errors='coerce')

    # Drop NaN values
    series = series.dropna()

    # Calculate statistics
    stats = series.describe()

    # Add additional statistics
    stats['std'] = series.std()
    stats['skewness'] = series.skew()
    stats['kurtosis'] = series.kurtosis()

    return stats


def get_frequency_distribution(db, field, subfield=None, teacher=None, class_name=None, start_date=None, end_date=None):
    pipeline = []
    
    # Use the build_query function to create the initial match stage
    match_query = build_query( teacher=teacher, class_name=class_name, start_date=start_date, end_date=end_date)

    
    
    if match_query:
        pipeline.append({'$match': match_query})
    
    if subfield:
        pipeline.extend([
            {"$unwind": "$questions"},  # Unwind the questions array
            {"$group": {
                "_id": f"$questions.{subfield}",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ])
    else:
        pipeline.extend([
            {"$group": {
                "_id": f"${field}",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ])
    
    result = list(db.tests.aggregate(pipeline))
    return result # for display


def performance_trend(collection, query=None):
    pipeline = []

    # Add the query to the pipeline if provided
    if query:
        pipeline.append({"$match": query})

    pipeline.extend([
        {"$unwind": "$test_results"},
        {"$project": {
            "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$test_results.date"}},
            "percentage": {"$toDouble": "$test_results.overall_percentage"}
        }},
        {"$group": {
            "_id": "$date",
            "values": {"$push": "$percentage"}
        }},
        {"$project": {
            "date": "$_id",
            "values": {
                "$filter": {
                    "input": "$values",
                    "as": "value",
                    "cond": {"$and": [
                        {"$ne": ["$$value", None]},
                        {"$ne": ["$$value", {"$literal": float('nan')}]}
                    ]}
                }
            }
        }},
        {"$project": {
            "date": 1,
            "count": {"$size": "$values"},
            "avg_performance": {"$avg": "$values"},
            "min_value": {"$min": "$values"},
            "max_value": {"$max": "$values"}
        }},
        {"$sort": SON([("date", 1)])}
    ])

    results = list(collection.aggregate(pipeline))

    # Transform results into a list of dictionaries
    trend_data = [
        {
            "date": result["date"],
            "count": result["count"],
            "avg_performance": result["avg_performance"],
            "min_value": result["min_value"],
            "max_value": result["max_value"]
        }
        for result in results
    ]

    return trend_data


def performance_trend_pandas(collection):
    pipeline = [
        {"$unwind": "$test_results"},
        {"$project": {
            "date": "$test_results.date",
            "overall_percentage": "$test_results.overall_percentage"
        }}
    ]
    data = list(collection.aggregate(pipeline))

    df = pd.DataFrame(data)
    df['overall_percentage'] = pd.to_numeric(
        df['overall_percentage'], errors='coerce')
    df['date'] = pd.to_datetime(df['date']).dt.date

    trend = df.groupby('date')['overall_percentage'].agg(
        ['mean', 'count']).reset_index()
    trend = trend.sort_values('date')

    return trend


def correlation(collection, field1, field2, query=None):
    pipeline = []
    
    if query:
        pipeline.append({"$match": query})
    
    pipeline.extend([
        {"$unwind": "$test_results"},
        {"$group": {
            "_id": None,
            "x_avg": {"$avg": f"$test_results.{field1}"},
            "y_avg": {"$avg": f"$test_results.{field2}"},
            "x_std": {"$stdDevPop": f"$test_results.{field1}"},
            "y_std": {"$stdDevPop": f"$test_results.{field2}"},
            "cov": {
                "$avg": {
                    "$multiply": [
                        {"$subtract": [f"$test_results.{field1}", {
                            "$avg": f"$test_results.{field1}"}]},
                        {"$subtract": [f"$test_results.{field2}", {
                            "$avg": f"$test_results.{field2}"}]}
                    ]
                }
            }
        }},
        {"$project": {
            "correlation": {
                "$divide": [
                    "$cov",
                    {"$multiply": ["$x_std", "$y_std"]}
                ]
            }
        }}
    ])
    
    result = list(collection.aggregate(pipeline))
    return result[0]['correlation'] if result else None


def identify_students_with_nan(collection, fields_to_check, query=None):
    pipeline = []
    
    if query:
        pipeline.append({"$match": query})
    
    pipeline.extend([
        {"$unwind": "$test_results"},
        {"$project": {
            "student_id": 1,
            "first_name": 1,
            "last_name": 1,
            "teacher": 1,
            "test_id": "$test_results.test_id",
            "date": "$test_results.date",
            **{field: f"$test_results.{field}" for field in fields_to_check},
            **{f"{field}_is_nan": {
                "$or": [
                    {"$eq": [f"$test_results.{field}", None]},
                    {"$eq": [f"$test_results.{field}", "NaN"]},
                    {"$eq": [{"$type": f"$test_results.{field}"}, "missing"]}
                ]
            } for field in fields_to_check}
        }},
        {"$match": {"$or": [{f"{field}_is_nan": True}
                            for field in fields_to_check]}},
        {"$project": {
            "student_id": 1,
            "first_name": 1,
            "last_name": 1,
            "test_id": 1,
            "date": 1,
            "teacher": 1,
            **{field: 1 for field in fields_to_check},
            "_id": 0
        }}
    ])

    return list(collection.aggregate(pipeline))


def check_responses_for_nan(collection, query=None):
    pipeline = []
    
    if query:
        pipeline.append({"$match": query})
    
    pipeline.extend([
        {"$unwind": "$test_results"},
        {"$unwind": "$test_results.responses"},
        {"$match": {
            "$or": [
                {"test_results.responses.response": None},
                {"test_results.responses.response": "NaN"},
                {"test_results.responses.response": {"$exists": False}}
            ]
        }},
        {"$group": {
            "_id": {
                "student_id": "$student_id",
                "first_name": "$first_name",
                "last_name": "$last_name",
                "test_id": "$test_results.test_id",
                "date": "$test_results.date"
            },
            "unanswered_questions": {"$push": "$test_results.responses.question"}
        }},
        {"$project": {
            "student_id": "$_id.student_id",
            "first_name": "$_id.first_name",
            "last_name": "$_id.last_name",
            "test_id": "$_id.test_id",
            "date": "$_id.date",
            "unanswered_count": {"$size": "$unanswered_questions"},
            "unanswered_questions": 1,
            "_id": 0
        }}
    ])

    return list(collection.aggregate(pipeline))



def create_interactive_student_table(missed_test_df, width='100%', height='600px', highlight_color='#ADD8E6'):
    # Extract class name and test name from test_id
    missed_test_df['class_name'] = missed_test_df['test_id'].str.split('_').str[0]
    missed_test_df['test_name'] = missed_test_df['test_id'].str.split('_').str[1:-1].str.join('_')
    
    # Group by student and count missed tests
    student_summary = missed_test_df.groupby(['student_id', 'first_name', 'last_name', 'teacher']).size().reset_index(name='missed_tests_count')

    app = Dash(__name__)

    app.layout = html.Div([
        dcc.Input(id="search-input", type="text", placeholder="Search by name or teacher...", style={'width': '100%', 'marginBottom': '10px'}),
        dash_table.DataTable(
            id='student-table',
            columns=[{"name": i, "id": i} for i in student_summary.columns],
            data=student_summary.to_dict('records'),
            page_size=10,
            style_table={'height': height, 'overflowY': 'auto'},
            style_cell={
                'textAlign': 'left',
                'font-family': 'Arial, sans-serif',
                'padding': '5px'
            },
            style_header={
                'backgroundColor': 'lightgrey',
                'fontWeight': 'bold'
            },
            style_data_conditional=[
                {
                    'if': {'row_index': 'odd'},
                    'backgroundColor': 'rgb(248, 248, 248)'
                },
                {
                    'if': {'state': 'selected'},
                    'backgroundColor': highlight_color,
                    'border': f'1px solid {highlight_color}'
                }
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

    @callback(
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

    @callback(
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
                
                # Format dates to exclude time
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

    return app

def display_interactive_student_table(missed_test_df, width='100%', height='600px', highlight_color='#FAD1BB'):
    app = create_interactive_student_table(missed_test_df, width, height, highlight_color)
    app.run_server(debug=True, port=8051)


def create_performance_graph(performance_by_standard):
    df = performance_by_standard

    layout = html.Div([
        html.H1("Student Performance Tracker", style={'textAlign': 'center'}),
        html.Div([
            html.Label("Select a Class:", style={'fontWeight': 'bold'}),
            dcc.Dropdown(
                id='class-dropdown',
                options=[{'label': i, 'value': i} for i in df['class_name'].unique()],
                placeholder="Select a class",
            ),
        ], style={'marginBottom': '20px'}),
        html.Div([
            html.Label("Select a Student:", style={'fontWeight': 'bold'}),
            dcc.Dropdown(
                id='student-dropdown',
                placeholder="First select a class",
            ),
        ], style={'marginBottom': '20px'}),
        dcc.Graph(id='progress-graph')
    ])

    def register_callbacks(app):
        @app.callback(
            Output('student-dropdown', 'options'),
            Output('student-dropdown', 'placeholder'),
            Input('class-dropdown', 'value')
        )
        def set_student_options(selected_class):
            if not selected_class:
                return [], "First select a class"
            dff = df[df['class_name'] == selected_class]
            options = [{'label': f"{row['first_name']} {row['last_name']}", 'value': row['student_id']} 
                       for _, row in dff.drop_duplicates(['student_id', 'first_name', 'last_name']).iterrows()]
            return options, "Select a student"

        @app.callback(
            Output('progress-graph', 'figure'),
            Input('class-dropdown', 'value'),
            Input('student-dropdown', 'value')
        )
        def update_graph(selected_class, selected_student):
            if not selected_class or not selected_student:
                return go.Figure()

            dff = df[(df['class_name'] == selected_class) & (df['student_id'] == selected_student)]
            
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=dff['standard'],
                y=dff['avg_performance'],
                marker_color='#20C997',  # Teal color
                name='Performance',
                text=dff['avg_performance'].apply(lambda x: f'{x:.1f}%'),
                textposition='auto',
                hovertemplate='Standard: %{x}<br>Performance: %{y:.1f}%<br>Total Questions: %{customdata}<extra></extra>',
                customdata=dff['total_questions']
            ))
            fig.add_trace(go.Bar(
                x=dff['standard'],
                y=[100]*len(dff),
                marker_color='rgba(32, 201, 151, 0.2)',  # Lighter shade of teal
                name='Total',
                hoverinfo='skip'
            ))

            fig.update_layout(
                title=f"Performance by Standard for {dff['first_name'].iloc[0]} {dff['last_name'].iloc[0]}",
                xaxis_title="Standard",
                yaxis_title="Performance (%)",
                barmode='overlay',
                bargap=0.1,
                plot_bgcolor='rgba(32, 201, 151, 0.05)',  # Very light teal background
            )

            return fig

    return layout, register_callbacks


def create_performance_dash_app(performance_by_standard):
    app = dash.Dash(__name__, suppress_callback_exceptions=True)
    layout, register_callbacks = create_performance_graph(performance_by_standard)
    app.layout = layout
    register_callbacks(app)
    app.run_server(debug=True, port=8052)



def create_standards_difficulty_graph(standard_difficulty):
    def create_layout():
        return html.Div([
            html.H1("Standards Ranked by Difficulty"),
            dcc.Dropdown(
                id='sort-dropdown',
                options=[
                    {'label': 'Sort by Difficulty Rank', 'value': 'difficulty_rank'},
                    {'label': 'Sort by Average Performance', 'value': 'avg_performance'},
                    {'label': 'Sort by Total Questions', 'value': 'total_questions'},
                    {'label': 'Sort by Unique Students', 'value': 'unique_students'}
                ],
                value='difficulty_rank',
                style={'width': '50%'}
            ),
            dcc.Graph(id='difficulty-graph')
        ])

    def register_callbacks(app):
        @app.callback(
            Output('difficulty-graph', 'figure'),
            Input('sort-dropdown', 'value')
        )
        def update_graph(sort_by):
            df_sorted = standard_difficulty.sort_values(sort_by, ascending=False if sort_by == 'avg_performance' else True)
            
            fig = go.Figure()

            fig.add_trace(go.Bar(
                x=df_sorted['standard'],
                y=df_sorted['avg_performance'],
                hovertemplate='<b>Standard:</b> %{x}<br>' +
                              '<b>Avg Performance:</b> %{y:.2f}%<br>' +
                              '<b>Total Questions:</b> %{customdata[0]}<br>' +
                              '<b>Unique Students:</b> %{customdata[1]}<br>' +
                              '<b>Difficulty Rank:</b> %{customdata[2]}' +
                              '<extra></extra>',
                customdata=df_sorted[['total_questions', 'unique_students', 'difficulty_rank']],
                marker_color=df_sorted['avg_performance'],
                marker_colorscale='Earth',
                marker_colorbar=dict(title='Avg Performance (%)')
            ))

            fig.update_layout(
                title='Standards Ranked by Difficulty',
                xaxis_title='Standard',
                yaxis_title='Average Performance (%)',
                yaxis_range=[0, 100],
                hoverlabel=dict(bgcolor="white", font_size=12),
                margin=dict(l=50, r=50, t=50, b=100)
            )

            fig.update_xaxes(tickangle=45)

            return fig

    return create_layout, register_callbacks

def display_standards_difficulty_graph(standard_difficulty):
    app = dash.Dash(__name__)
    layout, register_callbacks = create_standards_difficulty_graph(standard_difficulty)
    app.layout = layout()
    register_callbacks(app)
    app.run_server(debug=True, port=8053)


def create_question_type_difficulty_graph(question_type_difficulty):
    
    df = question_type_difficulty

    layout = html.Div([
        html.H1("Question Types Ranked by Difficulty"),
        dcc.Dropdown(
            id='sort-dropdown',
            options=[
                {'label': 'Sort by Difficulty Rank', 'value': 'difficulty_rank'},
                {'label': 'Sort by Average Performance', 'value': 'avg_performance'},
                {'label': 'Sort by Total Questions', 'value': 'total_questions'},
                {'label': 'Sort by Unique Students', 'value': 'unique_students'}
            ],
            value='difficulty_rank',
            style={'width': '50%'}
        ),
        dcc.Graph(id='difficulty-graph')
    ])

    def register_callbacks(app):
        @app.callback(
            Output('difficulty-graph', 'figure'),
            Input('sort-dropdown', 'value')
        )

        def update_graph(sort_by):
            df_sorted = df.sort_values(sort_by, ascending=False if sort_by == 'avg_performance' else True)
            
            fig = go.Figure()

            # Add the bar chart
            fig.add_trace(go.Bar(
                x=df_sorted['question_type'],
                y=df_sorted['avg_performance'],
                hovertemplate='<b>Question Type:</b> %{x}<br>' +
                            '<b>Avg Performance:</b> %{y:.2f}%<br>' +
                            '<b>Total Questions:</b> %{customdata[0]}<br>' +
                            '<b>Unique Students:</b> %{customdata[1]}<br>' +
                            '<b>Difficulty Rank:</b> %{customdata[2]}' +
                            '<extra></extra>',
                customdata=df_sorted[['total_questions', 'unique_students', 'difficulty_rank']],
                marker_color=df_sorted['avg_performance'],
                marker_colorscale='Earth',
                marker_colorbar=dict(title='Avg Performance (%)')
            ))

            # Update layout
            fig.update_layout(
                title='Question Types Ranked by Difficulty',
                xaxis_title='Question Type',
                yaxis_title='Average Performance (%)',
                yaxis_range=[0, 100],
                hoverlabel=dict(bgcolor="white", font_size=12),
                margin=dict(l=50, r=50, t=50, b=100)  # Increase bottom margin for x-axis labels
            )

            # Rotate x-axis labels for better readability
            fig.update_xaxes(tickangle=45)

            return fig
    
    return layout, register_callbacks

def display_question_type_difficulty_graph(question_type_difficulty):
    app = dash.Dash(__name__)
    layout, register_callbacks = create_question_type_difficulty_graph(question_type_difficulty)
    app.layout = layout
    register_callbacks(app)
    app.run_server(debug=True, port=8054)


def create_performance_figure(identifier, df, performance_trend_df, top_n_standards=5, specific_standards=None, use_name=False):
    if use_name:
        if isinstance(identifier, tuple) and len(identifier) == 2:
            first_name, last_name = identifier
            student_data = df[(df['first_name'] == first_name) & (df['last_name'] == last_name)]
        elif isinstance(identifier, str):
            student_data = df[df['first_name'].str.contains(identifier, case=False) | 
                              df['last_name'].str.contains(identifier, case=False)]
        else:
            raise ValueError("When use_name is True, identifier should be a tuple (first_name, last_name) or a string.")
        if student_data.empty:
            return go.Figure()  # Return empty figure if no data found
        student_data = student_data.reset_index(drop=True)
        student_id = student_data['student_id'].iloc[0]
    else:
        student_id = identifier
        student_data = df[df['student_id'] == student_id]

    if student_data.empty:
        return go.Figure()  # Return empty figure if no data found

    student_name = f"{student_data['first_name'].iloc[0]} {student_data['last_name'].iloc[0]}"
    
    student_performance = student_data.groupby(['date', 'test_id'])['is_correct'].mean().reset_index()
    student_performance['avg_performance'] = student_performance['is_correct'] * 100

    start_date = student_performance['date'].min()
    end_date = student_performance['date'].max()

    # Filter group_avg to only include dates where the student has data
    group_avg = performance_trend_df[
        (performance_trend_df['date'].isin(student_performance['date']))
    ]

    if specific_standards:
        top_standards = [std for std in specific_standards if std in student_data['standard'].unique()]
    else:
        top_standards = student_data.groupby('standard')['is_correct'].mean().nlargest(top_n_standards).index

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=group_avg['date'], 
        y=group_avg['avg_performance'],
        mode='lines',
        name='Class Average',
        line=dict(color='gray', dash='dash')
    ))

    fig.add_trace(go.Scatter(
        x=student_performance['date'], 
        y=student_performance['avg_performance'],
        mode='lines+markers',
        name=f'{student_name} Overall',
        line=dict(color='blue'),
        text=[f"<b>Test:</b> {test}<br><b>Date:</b> {date}<br><b>Overall:</b> {perf:.2f}%<br>Click for details" 
              for test, date, perf in zip(student_performance['test_id'], 
                                          student_performance['date'], 
                                          student_performance['avg_performance'])],
        hovertemplate="%{text}<extra></extra>"
    ))

    for standard in top_standards:
        standard_data = student_data[student_data['standard'] == standard]
        standard_performance = standard_data.groupby('date')['is_correct'].mean() * 100
        fig.add_trace(go.Scatter(
            x=standard_performance.index, 
            y=standard_performance.values,
            mode='markers',
            name=f'Standard: {standard}',
            marker=dict(size=10)
        ))

    avg_performance = student_performance['avg_performance'].mean()
    fig.add_shape(
        type="line",
        x0=start_date,
        y0=avg_performance,
        x1=end_date,
        y1=avg_performance,
        line=dict(color="red", width=2, dash="dot"),
        opacity=0.5
    )
    fig.add_trace(go.Scatter(
        x=[start_date],
        y=[avg_performance],
        mode="lines",
        name=f"Student Average: {avg_performance:.2f}%",
        line=dict(color="red", width=2, dash="dot"),
        opacity=0.5
    ))

    fig.update_layout(
        title=f'Performance Over Time - {student_name} (ID: {student_id}) vs Class Average',
        xaxis_title='Date',
        yaxis_title='Average Performance (%)',
        legend=dict(x=1.05, y=1, bordercolor='Black', borderwidth=1),
        hovermode='closest',
        yaxis=dict(range=[0, 105])
    )

    return fig

def create_breakdown_figure(student_data, test_id, date):
    test_data = student_data[(student_data['test_id'] == test_id) & (student_data['date'] == date)]
    standard_breakdown = test_data.groupby('standard')['is_correct'].mean() * 100
    
    colors = ['#FF4136', '#FFDC00', '#2ECC40', '#0074D9']  # Red, Yellow, Green, Blue
    color_thresholds = [0, 70, 80, 90, 100]
    
    def get_color(val):
        for i, threshold in enumerate(color_thresholds[1:], 1):
            if val < threshold:
                return colors[i-1]
        return colors[-1]  # Return the last color if val is 100
    
    bar_colors = [get_color(val) for val in standard_breakdown.values]
    
    breakdown_fig = go.Figure(data=[go.Bar(
        x=standard_breakdown.index,
        y=standard_breakdown.values,
        text=standard_breakdown.values.round(2),
        textposition='auto',
        marker_color=bar_colors
    )])
    
    class_name, *test_name_parts = test_id.split('_')
    test_name = ' '.join(test_name_parts[:-1])
    
    formatted_date = pd.to_datetime(date).strftime('%Y-%m-%d')
    
    breakdown_fig.update_layout(
        title=f'Standard Breakdown for {class_name}: {test_name}<br>Date: {formatted_date}',
        xaxis_title='Standard',
        yaxis_title='Performance (%)',
        yaxis=dict(range=[0, 105])
    )
    
    return breakdown_fig

def create_dash_app(df, performance_trend_df, top_n_standards=5, specific_standards=None):
    app = Dash(__name__)

    # Define styles
    input_style = {
        'fontSize': '18px',
        'padding': '10px',
        'width': '300px',
        'marginRight': '10px',
        'marginBottom': '10px'
    }

    checklist_style = {
        'fontSize': '18px',
        'marginBottom': '10px'
    }

    app.layout = html.Div([
        dcc.Input(
            id='student-identifier', 
            type='text', 
            placeholder='Enter Student ID or Name',
            style=input_style
        ),
        dcc.Checklist(
            id='use-name',
            options=[{'label': 'Use Name Instead of ID', 'value': 'use_name'}],
            value=[],
            style=checklist_style
        ),
        dcc.Input(
            id='top-n-standards', 
            type='number', 
            placeholder='Number of top standards', 
            value=top_n_standards,
            style=input_style
        ),
        dcc.Input(
            id='specific-standards', 
            type='text', 
            placeholder='Specific standards (comma-separated)',
            style=input_style
        ),
        html.Div(id='breakdown-container'),
        dcc.Graph(id='performance-graph')
    ])

    @app.callback(
        Output('performance-graph', 'figure'),
        Input('student-identifier', 'value'),
        Input('use-name', 'value'),
        Input('top-n-standards', 'value'),
        Input('specific-standards', 'value')
    )
    def update_graph(identifier, use_name, top_n, specific_stds):
        if not identifier:
            return go.Figure()
        use_name = 'use_name' in use_name
        if specific_stds:
            specific_stds = [s.strip() for s in specific_stds.split(',')]
        else:
            specific_stds = None
        try:
            return create_performance_figure(identifier, df, performance_trend_df, top_n_standards=top_n, specific_standards=specific_stds, use_name=use_name)
        except ValueError as e:
            return go.Figure().add_annotation(text=str(e), showarrow=False, font=dict(size=20))

    @app.callback(
        Output('breakdown-container', 'children'),
        Input('performance-graph', 'clickData'),
        State('student-identifier', 'value'),
        State('use-name', 'value')
    )
    def display_breakdown(clickData, identifier, use_name):
        if clickData is None:
            return "Click on a point to see breakdown"
        
        point = clickData['points'][0]
        date = point['x']
        
        # Extract test_id more robustly
        text_parts = point['text'].split('<br>')
        test_part = next((part for part in text_parts if part.startswith('<b>Test:</b>')), None)
        
        if test_part:
            test_id = test_part.replace('<b>Test:</b>', '').strip()
        else:
            return "Unable to determine test ID from clicked point"
        
        use_name = 'use_name' in use_name
        if use_name:
            if isinstance(identifier, str):
                student_data = df[df['first_name'].str.contains(identifier, case=False) | 
                                df['last_name'].str.contains(identifier, case=False)]
            else:
                return "Invalid identifier for name search"
        else:
            student_data = df[df['student_id'] == identifier]
        
        if student_data.empty:
            return "No data found for the given identifier"
        
        breakdown_fig = create_breakdown_figure(student_data, test_id, date)
        
        return dcc.Graph(figure=breakdown_fig)

    return app

def display_performance_figure(df, performance_trend_df, top_n_standards=5, specific_standards=None, port=8055):
    app = create_dash_app(df, performance_trend_df, top_n_standards, specific_standards)
    app.run_server(debug=True, port=port)