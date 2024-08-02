import dash
from dash import html, dcc, Input, Output
import plotly.graph_objs as go
from shared_data import get_data, logger

import sys
import os

# Get the absolute path of the project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Add the project root to the Python path
sys.path.insert(0, project_root)

def process_question_type_difficulty(df):
    """Process the dataframe to calculate question type difficulty."""
    question_type_difficulty = df.groupby('question_type').agg({
        'is_correct': ['mean', 'count'],
        'student_id': 'nunique'
    }).reset_index()

    question_type_difficulty.columns = ['question_type', 'avg_performance', 'total_questions', 'unique_students']
    question_type_difficulty['avg_performance'] = (question_type_difficulty['avg_performance'] * 100).round(2)
    question_type_difficulty = question_type_difficulty.sort_values('avg_performance', ascending=True)
    question_type_difficulty['difficulty_rank'] = question_type_difficulty['avg_performance'].rank(method='dense', ascending=True)

    return question_type_difficulty

def create_dash_layout():
    """Create the Dash app layout."""
    return html.Div([
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

def register_callbacks(app, df):
    """Register callbacks for the Dash app."""
    @app.callback(
        Output('difficulty-graph', 'figure'),
        Input('sort-dropdown', 'value')
    )
    def update_graph(sort_by):
        df_sorted = df.sort_values(sort_by, ascending=False if sort_by == 'avg_performance' else True)
        
        fig = go.Figure()

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

        fig.update_layout(
            title='Question Types Ranked by Difficulty',
            xaxis_title='Question Type',
            yaxis_title='Average Performance (%)',
            yaxis_range=[0, 100],
            hoverlabel=dict(bgcolor="white", font_size=12),
            margin=dict(l=50, r=50, t=50, b=100)
        )

        fig.update_xaxes(tickangle=45)

        return fig

def create_question_type_difficulty_app(df):
    """Create and return the Dash app for question type difficulty."""
    logger.info("Creating question type difficulty app")
    question_type_difficulty = process_question_type_difficulty(df)  # Process the data for this specific app
    
    app = dash.Dash(__name__)
    server = app.server
    app.layout = create_dash_layout()
    register_callbacks(app, question_type_difficulty)
    
    logger.info("Question type difficulty app created successfully")
    return app, server

app, server = create_question_type_difficulty_app(get_data(anonymize=True))

if __name__ == "__main__":
    logger.info("Starting standalone app")
    app, server = create_question_type_difficulty_app(anonymize=True)
    logger.info("Running server")
    app.run_server(debug=True, port=8054)