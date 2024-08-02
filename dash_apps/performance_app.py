import dash
from dash import html, dcc, Input, Output
import plotly.graph_objs as go
import sys
import os

# Get the absolute path of the project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Add the project root to the Python path
sys.path.insert(0, project_root)

from shared_data import get_data, logger

def process_performance_data(df):
    """Process the performance data."""
    performance_by_standard = df.groupby(['student_id', 'first_name', 'last_name', 'standard', 'class_name']).agg({
        'is_correct': ['mean', 'count']
    }).reset_index()
    performance_by_standard.columns = ['student_id', 'first_name', 'last_name', 'standard', 'class_name', 'avg_performance', 'total_questions']
    performance_by_standard['avg_performance'] *= 100  # Convert to percentage
    performance_by_standard['avg_performance'] = performance_by_standard['avg_performance'].round(2)
    return performance_by_standard

def create_dash_layout(df):
    """Create the Dash app layout."""
    return html.Div([
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

def register_callbacks(app, df):
    """Register callbacks for the Dash app."""
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
            marker_color='#20C997',
            name='Performance',
            text=dff['avg_performance'].apply(lambda x: f'{x:.1f}%'),
            textposition='auto',
            hovertemplate='Standard: %{x}<br>Performance: %{y:.1f}%<br>Total Questions: %{customdata}<extra></extra>',
            customdata=dff['total_questions']
        ))
        fig.add_trace(go.Bar(
            x=dff['standard'],
            y=[100]*len(dff),
            marker_color='rgba(32, 201, 151, 0.2)',
            name='Total',
            hoverinfo='skip'
        ))

        fig.update_layout(
            title=f"Performance by Standard for {dff['first_name'].iloc[0]} {dff['last_name'].iloc[0]}",
            xaxis_title="Standard",
            yaxis_title="Performance (%)",
            barmode='overlay',
            bargap=0.1,
            plot_bgcolor='rgba(32, 201, 151, 0.05)',
        )

        return fig

def create_performance_dash_app(df):
    """Create and return the Dash app for the performance tracker."""
    logger.info("Creating performance dash app")
    performance_by_standard = process_performance_data(df)
    
    app = dash.Dash(__name__, suppress_callback_exceptions=True)
    app.layout = create_dash_layout(performance_by_standard)
    register_callbacks(app, performance_by_standard)
    
    logger.info("Performance dash app created successfully")
    return app

if __name__ == "__main__":
    logger.info("Starting standalone app")
    app = create_performance_dash_app(anonymize=True)
    logger.info("Running server")
    app.run_server(debug=True, port=8052)