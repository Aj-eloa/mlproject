import dash
from dash import html, dcc, Input, Output, State
import plotly.graph_objs as go
import pandas as pd
import sys
import os
# Get the absolute path of the project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Add the project root to the Python path
sys.path.insert(0, project_root)
from src.components.db_connection import build_query, get_database, logger
from src.pipelines import mongo_db_pipelines as m_db



from shared_data import get_data, logger
from src.utils import performance_trend

def process_performance_trend(df, query):
    trend_data = performance_trend(df, query)
    performance_trend_df = pd.DataFrame(trend_data)
    if 'date' in performance_trend_df.columns:
        performance_trend_df['date'] = pd.to_datetime(performance_trend_df['date'])
    return performance_trend_df


# Figure creation functions
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

# Dash app layout and callbacks
def create_dash_layout():
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
    
    return html.Div([
        dcc.Input(id='student-identifier', type='text', placeholder='Enter Student ID or Name', style=input_style),
        dcc.Checklist(id='use-name', options=[{'label': 'Use Name Instead of ID', 'value': 'use_name'}], value=[], style=checklist_style),
        dcc.Input(id='top-n-standards', type='number', placeholder='Number of top standards', value=5, style=input_style),
        dcc.Input(id='specific-standards', type='text', placeholder='Specific standards (comma-separated)', style=input_style),
        html.Div(id='breakdown-container'),
        dcc.Graph(id='performance-graph')
    ])

def register_callbacks(app, df, performance_trend_df):
    @app.callback(
        Output('performance-graph', 'figure'),
        [Input('student-identifier', 'value'),
         Input('use-name', 'value'),
         Input('top-n-standards', 'value'),
         Input('specific-standards', 'value')]
    )
    def update_graph(identifier, use_name, top_n, specific_stds):
        if not identifier:
            return go.Figure()
        use_name = 'use_name' in use_name
        specific_stds = [s.strip() for s in specific_stds.split(',')] if specific_stds else None
        try:
            return create_performance_figure(identifier, df, performance_trend_df, top_n_standards=top_n, specific_standards=specific_stds, use_name=use_name)
        except ValueError as e:
            return go.Figure().add_annotation(text=str(e), showarrow=False, font=dict(size=20))

    @app.callback(
        Output('breakdown-container', 'children'),
        [Input('performance-graph', 'clickData')],
        [State('student-identifier', 'value'),
         State('use-name', 'value')]
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

def create_comprehensive_dash_app(df, custom_query=None):
    """Create and return the Dash app for performance visualization."""
    logger.info("Starting creation of performance dash app")

    logger.info('Retrieved data from shared module')
    
    # Ensure 'date' column exists and is in datetime format
    if 'date' not in df.columns:
        logger.info("Creating 'date' column from 'test_id'")
        df['date'] = pd.to_datetime(df['test_id'].str.split('_').str[-1], format='%Y%m%d')
    df['date'] = pd.to_datetime(df['date'])
    
    # Get the database connection
    db = get_database(create_indices=True)
    students = db['students']
    
    # Use custom query if provided, otherwise use default
    query = custom_query if custom_query else None
    logger.info(f"Using query: {query}")
    
    performance_trend_df = process_performance_trend(students, query)  
    
    app = dash.Dash(__name__)
    server = app.server
    app.layout = create_dash_layout()
    register_callbacks(app, df, performance_trend_df)
    
    logger.info("Performance dash app created successfully")
    return app, server

app, server = create_comprehensive_dash_app(get_data(anonymize=True))

# This is used when running the app standalone
if __name__ == '__main__':
    logger.info("Starting standalone app")
    # Example of how you could pass a custom query
    # custom_query = {"some_field": "some_value"}
    df = get_data(anonymize=True)
    app, server = create_comprehensive_dash_app(df)  # Or pass custom_query here if needed
    logger.info("Running server")
    app.run_server(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8055)))


