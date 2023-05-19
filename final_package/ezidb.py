#!/usr/bin/env python
# coding: utf-8
import sys
import os
import json
import pandas as pd
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
import pycountry
import plotly.graph_objs as go
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import dash
import dash_auth
from dash import dash_table
from dash.dash_table.Format import Group
from dash import html, dcc
from dash.dependencies import Input, Output, State, ClientsideFunction, MATCH, ALL, ClientsideFunction
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import time
from datetime import datetime, date, time, timedelta
from dateutil.relativedelta import relativedelta
#import mysql.connector
import pymysql
pymysql.install_as_MySQLdb()
from flask_caching import Cache
#from dash_extensions.enrich import DashProxy, Output, Input, State, ServersideOutput, ServersideOutputTransform
from credentials import VALID_USERNAME_PASSWORD_PAIRS
import webbrowser as web
from threading import Timer

# Call data preprocessing function to preprocess data
data = None  # Set global_data to None to force a reload of data
#web.open_new_tab('http://127.0.0.1:8090/')
def open_browser():
    web.open_new("http://localhost:{}".format(8090))

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.UNITED], meta_tags=[{"name": "viewport", "content": "width=device-width"}])
app.title = 'Dashboard'
auth = dash_auth.BasicAuth(app, VALID_USERNAME_PASSWORD_PAIRS)

# Create a Flask-Caching object
cache = Cache(app.server, config={
    'CACHE_TYPE': 'filesystem',
    'CACHE_DIR': 'cache-directory',
    'CACHE_DEFAULT_TIMEOUT': 86400  # 24 hours
})
cache.clear()

# Create a dcc.Store component to store the data
store = dcc.Store(id='local', storage_type='local')
# Get the path of the current script
current_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))

# define a function to preprocess the data
def preprocess_data(df):
    df = df[['sales_order_id','date','id','created_at','quantity','sku','name','name_i','face_price','currency', 
                    'country','state_i', 'state_o','status','external_unit_price', 'name_o',
                   'city', 'country_o']]
    df["created_at"] = df["created_at"].astype('datetime64[ns]')
    df["date"] = pd.to_datetime(df["date"])
    df[['year', 'month', 'day', 'weekday']] = df['created_at'].apply(lambda x: pd.Series([x.year, x.month, x.day, x.day_name()]))
    df[['quantity',  'id']] = df[['quantity','id']].astype('Int64')
    #df[['product_id', 'customer_company_id']] = df[[ 'product_id', 'customer_company_id']].astype('Int64')
    df['face_price'] = df['face_price'].astype('float').round(2)
    df['price'] = df['external_unit_price'].str.extract('(\d+)').astype('float') / 100
    df['price'] = df['price'].round(2)
    df['total'] = (df['quantity'] * df['price']).round(2)
    df.sort_values(['created_at'],ascending=[True])
    return df

#load data for current data
def load_current():
    csv_files = ['current.csv', 'currentsql.csv']
    csv_paths = [os.path.join(current_dir, file) for file in csv_files]
    latest_file = max(csv_paths, key=os.path.getmtime)
    data = pd.read_csv(latest_file)
    clean_data = preprocess_data(data)
    return clean_data

# Set up the database connection
def get_database_connection():
    connection = pymysql.connect(
        host = '127.0.0.1',
        user = 'readonly',
        password = 'MwLvD9DFL8mnrTKkI6fU',
        port = 3335
        #DB_NAME = 'mydatabase',
    )
    return connection

# Read data from the database and store it in csv
def load_current_sql():
    connection = get_database_connection()
    cursor = connection.cursor()
    last_date = "2023-01-01"
    last_date_o = "2023-01-01"
    query = f"""
            SELECT i.sales_order_id, i.id AS id, i.quantity, i.product_id, i.state AS state_i, i.status, i.created_at, i.external_unit_price,
                       p.id AS sku_id, p.sku, p.name, p.description, p.currency, p.brand_id, p.face_price, p.country, b.name AS name_i,
                       o.date, o.invoice_number, o.state AS state_o, o.customer_company_id, c.id AS cust_id, c.name AS name_o, a.city, a.country AS country_o, x.finance_number, x.sales_order_id AS sales_order_id_o
                        FROM (SELECT *
                              FROM ezscm_production.sales_order_items
                              WHERE created_at > '{last_date}')  AS i
                        LEFT OUTER JOIN (SELECT *
                                         FROM ezscm_production.sales_orders
                                         WHERE date > '{last_date_o}') AS o
                            ON o.id = i.sales_order_id
                        LEFT OUTER JOIN ezscm_production.products AS p
                            ON p.id = i.product_id
                        LEFT OUTER JOIN ezscm_production.brands AS b
                            ON p.brand_id = b.id
                        LEFT OUTER JOIN ezscm_production.companies AS c
                            ON o.customer_company_id = c.id
                        LEFT OUTER JOIN ezscm_production.addresses AS a
                            ON c.billing_address_id = a.id
                        LEFT OUTER JOIN ezscm_production.invoices AS x
                            ON o.invoice_number = x.finance_number
                            
                            ORDER BY id ASC
                """
    cursor.execute(query)
    rows = cursor.fetchall()
    data = pd.read_sql(query, connection)
    clean_df = preprocess_data(data)
    clean_df.to_csv('currentsql.csv', index=False)
    #cache.set('data', df.to_dict('records'))
    connection.close()
    #return pd.DataFrame.from_dict(df)
    return clean_df

@app.callback(Output('local', 'data'),
              Output("loading-fetch-data", "children"),
              Input('fetch-data-button', 'n_clicks'))
def fetch_data(n_clicks):
    if n_clicks is None or n_clicks == 0:
        # Try to load data from the cache or CSV file
        stored_data = cache.get('data')
        if stored_data is not None:
            # Use the data from the cache if available
            return stored_data, ''
        else:
            # Otherwise, load the most recent data from the CSV files
            clean_data = load_current()
            cache.set('data', clean_data.to_json(date_format='iso', orient='split'))
            if clean_data.empty:
                return '', html.Div([
                    html.P('Data not found. Click on "Fetch Data" button.')
                ])
            else:
                return clean_data.to_json(date_format='iso', orient='split'), ''  # clean_data.to_dict('records')
    else:
        # Fetch data from the database and convert to pandas DataFrame
        try:
            clean_df = load_current_sql()
            cache.set('data', clean_df.to_json(date_format='iso', orient='split'))
            return clean_df.to_json(date_format='iso', orient='split'), html.Div([
                html.P('Data fetched successfully')
            ])
        except Exception as e:
            return '', html.Div([
                html.P('Connect to MySQL please', style={'color': 'red'})
            ])

@app.callback(Output('table-container', 'children'),
              [Input('fetch-data-button', 'n_clicks'),
               State('local', 'data')])
def update_data(n_clicks, data):
    if n_clicks is None or n_clicks == 0:
        json_resp = fetch_data(0)[0]
    else:
        json_resp = fetch_data(1)[0]
    # Convert the JSON data to a DataFrame
    df = pd.read_json(json_resp, orient='split')
    # Get the last row of the DataFrame
    last_row = df.tail(1)
   # Return the table with the last row of data
    return html.Div()
    # return dbc.Container([
    #     html.H6('Last row of Data Table'),
    #     dash_table.DataTable(
    #         id='table',
    #         columns=[{"name": i, "id": i} for i in last_row.columns],
    #         data=last_row.to_dict('records'),
    #         style_cell={'textAlign': 'center'},
    #         style_header={
    #             'backgroundColor': 'rgb(230, 230, 230)',
    #             'fontWeight': 'bold'
    #         },
    #         style_data_conditional=[
    #             {
    #                 'if': {'row_index': 'odd'},
    #                 'backgroundColor': 'rgb(248, 248, 248)'
    #             }
    #         ]
    #     )
    # ])

def load_cached_data():
    cached_data = cache.get('data')
    if cached_data is not None:
        df = pd.read_json(cached_data, orient='split')
    else: 
        df = load_current()
    return df

def load_histo():
    df = load_cached_data()
    if df is None:
        return pd.DataFrame()
    past_file = os.path.join(current_dir, 'pastfour.csv')
    past_data = pd.read_csv(past_file)
    clean_past = preprocess_data(past_data)
    histo_df = pd.concat([clean_past, df]).drop_duplicates(keep='first').reset_index(drop=True)
    histo_df["created_at"] = histo_df["created_at"].astype('datetime64[ns]')
    histo_df = histo_df[histo_df['state_i'] == 'fulfilled']
    return histo_df

today_date = datetime.now().strftime("%Y-%m-%d")

navbar = dbc.Navbar(
    dbc.Container(
        [
            dbc.Row(
                [
                    dbc.Col(html.Img(src="db.png", height="20px"), width="auto", align="center"),
                    dbc.Col(dbc.NavbarBrand("EZi Dashboard", className="ml-2"), width="auto", align="center"),
                    dbc.Col(html.Div(id="today-date", children=today_date), width="auto", align="center"),
                    dbc.Col(
                        [
                            dbc.Button('Fetch Data', id='fetch-data-button', n_clicks=0, className="mr-2"),
                     dcc.Loading(
                                id="loading-fetch-data",
                                type="default",
                                children=[
                                    dbc.Button(id='query-status-button', children='',style={'width': 'auto', 'margin-left': '10px'})
                                ]
                            ),
                            html.Div(id='status'),
                        ],
                        width="auto", align="end",style={'display': 'flex', 'align-items': 'center'}
                    ),
                    #html.Button(id='page-load', n_clicks=0, style={'display': 'none'}),
                    html.Div(id='page-load', style={'display': 'none'}, children='page-load'),
                ],
                className="my-row",
                align="center",
            ),
            dbc.NavbarToggler(id="navbar-toggler"),
        ]
    ),
    color="light",
    dark=False,
    sticky="top",
)

# Define page layout
page_layout = dbc.Container([
    
    # Add top_level section
    dbc.Row([
                dbc.Col(dcc.DatePickerSingle(
                    id='date-picker',
                    min_date_allowed=None,#data_df['date'].min(),
                    max_date_allowed=None,#data_df['date'].max(),
                    initial_visible_month=None,#data_df['date'].max(),
                    date=None, #data_df['date'].max()
                ),
                width=3
        ),
        dbc.Col(dbc.Card([
                    dbc.CardHeader("Overnight Orders, including not Complete"),
                    dbc.CardBody([html.P(id='overnight-sales')])
                ]),
                width=8
        ),

    ], justify="between", align="center", className='mb-4'),

    dbc.Card([
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Sales YtD"),
                        dbc.CardBody([
                            dcc.Graph(id='sales-chart-2')
                        ])
                    ], className="h-100", style={'height': '100%', 'display': 'flex', 'flex-direction': 'column'})
                ], sm=12, lg=4, className="mb-4"),
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader("Sales Mtd"),
                        dbc.CardBody([
                            dcc.Graph(id='sales-chart')
                        ])
                    ], className="h-100", style={'height': '100%', 'display': 'flex', 'flex-direction': 'column'})
                ], sm=12, lg=4, className="mb-4"),
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(
                            html.H6("Custs that did not create an order since.."),
                            style={'backgroundColor': '#F8F9FA'}
                        ),
                        dbc.CardBody(
                            dcc.Graph(
                                id='table',
                                config={'displayModeBar': False},
                                style={'padding': '0', 'margin': '0'}
                            )
                    )
                    ], className="h-100", style={'height': '100%', 'display': 'flex', 'flex-direction': 'column'})
                ], sm=12, lg=4, className="mb-4")
            ])
        ])
    ], className="rounded-0 border-0"),

    # Add rest of page layout here
    html.Div("Click on below tabs for further analysis 👇"),

], fluid=True, style={'padding': '2rem'})

@app.callback(
    Output('date-picker', 'min_date_allowed'),
    Output('date-picker', 'max_date_allowed'),
    Output('date-picker', 'initial_visible_month'),
    Output('date-picker', 'date'),
    Input('local', 'data'),
    #State('date-picker', 'date'),
)
def update_datepicker(data):
    df = load_cached_data()
    min_date_allowed = df['date'].astype('datetime64[ns]').min().strftime('%Y-%m-%d')
    max_date_allowed = df['date'].astype('datetime64[ns]').max().strftime('%Y-%m-%d')
    initial_visible_month = min_date_allowed
    date = df['date'].astype('datetime64[ns]').max().strftime('%Y-%m-%d')

    return min_date_allowed, max_date_allowed, initial_visible_month, date

today = pd.Timestamp.now().floor('D')
def prev_weekday(adate):
    adate -= timedelta(days=1)
    while adate.weekday() > 4: # Mon-Fri are 0-4
        adate -= timedelta(days=1)
    return adate

@app.callback(
    Output('overnight-sales', 'children'),
    [Input('date-picker', 'date'),
    State('local','data')],
)
def update_overnight_sales(date, data):
    df = load_cached_data()
    # Calculate overnight sales based on selected date
    overnight_sales = round(df[(df['date'] >= pd.Timestamp(date).floor('D'))]['total'].sum(), 2)
    overnight_sales = "{:,.2f}".format(overnight_sales)
    overnight_orders = df[(df['date'] >= pd.Timestamp(date).floor('D'))]['sales_order_id'].nunique()
    no_not_complete = df[(df['date'] >= pd.Timestamp(date).floor('D')) & (df['state_o']!='complete')]['sales_order_id'].nunique()
    so_not_complete = df[(df['date'] >= pd.Timestamp(date).floor('D')) & (df['state_o']!='complete')]['sales_order_id'].unique()
    links = [f"[{so}](https://ezi.ezcards.xyz/sales_orders/{so})" for so in so_not_complete]
    so_not_complete_str = ', '.join(links)
    return html.Div([
        f"O/N activity = $ {overnight_sales} from {overnight_orders} orders, where {no_not_complete} order(s) not fulfilled : ",
        html.Div(dcc.Markdown(so_not_complete_str))
    ])

#displaying gauge instead of bar chart for YTD
def new_sales_chart(date, df):
    current_year = pd.Timestamp(date).year
    current_month = pd.Timestamp(date).month
    current_day = pd.Timestamp(date).day
    prev_year = current_year - 1
    two_year = current_year - 2

    ytd_start = pd.to_datetime(f"{current_year}-01-01")
    last_ytd_start = pd.to_datetime(f"{prev_year}-01-01")
    last_ytd_end = pd.to_datetime(f"{prev_year}-{current_month}-{current_day}")
    two_ytd_start = pd.to_datetime(f"{two_year}-01-01")
    two_ytd_end = pd.to_datetime(f"{two_year}-{current_month}-{current_day}")

    sales_ytd = round(df[(df['date'] >= ytd_start)]['total'].sum(),2)
    sales_ytd_formatted = "{:,.2f}".format(sales_ytd)
    sales_ytd_last_year = df[(df['date'] >=last_ytd_start)& (df['date'] <= last_ytd_end)]['total'].sum()
    sales_ytd_two_year = df[(df['date'] >=two_ytd_start)& (df['date'] <= two_ytd_end)]['total'].sum()
    percent_vs_last_year_to_date = round(sales_ytd/sales_ytd_last_year*100,2)
    percent_vs_two_year_to_date = sales_ytd/sales_ytd_two_year 

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=percent_vs_last_year_to_date,
        gauge={
            'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': 'darkblue'},
            'bar': {'color': 'deepskyblue'},
            'bgcolor': 'white',
            'borderwidth': 2,
            'bordercolor': 'gray',
            'steps': [{'range': [0, 50], 'color': 'white'},
                      {'range': [50, 100], 'color': 'white'},
                      {'range': [100, 150], 'color': 'white'},
                      {'range': [1500, 200], 'color': 'white'}]
        },
        domain={'x': [0, 1], 'y': [0, 1]},
        #title={'text': "% of YtD vs past YtD sales"}
    ))

    # Add the sales_ytd string as a markdown string to the layout of the fig variable
    fig.update_layout(
        annotations=[
            go.layout.Annotation(
                x=0.5,
                y=1.2,
                showarrow=False,
                text=f"YTD Sales: $ {sales_ytd_formatted}",
                xref="paper",
                yref="paper",
                align='center',
                font=dict(size=18)
            ),
            go.layout.Annotation(
                x=0.5,
                y=-0.2,
                showarrow=False,
                text=f"{percent_vs_last_year_to_date}% generated vs past YtD sales",
                xref="paper",
                yref="paper",
                align='center',
                font=dict(size=18)
            )
        ]
    )
    
    return fig

@app.callback(
    Output('sales-chart-2', 'figure'),
    [Input('date-picker', 'date')],
    [State('local', 'data')]
)

def updated_new_sales_chart(date, data):
    current_year = pd.Timestamp(date).year
    ytd_start = pd.to_datetime(f"{current_year}-01-01")
    past_year = current_year - 1
    two_year = current_year - 2
    two_ytd_start = pd.to_datetime(f"{two_year}-01-01")
    
    # Load the data based on whether the CSV file exists or not
    if load_histo() is None:
        df = load_cached_data()
    else:
        df = load_histo()

    # Group the data by month and sum the sales
    fig = new_sales_chart(date, df)
    
    return fig

# displaying bar chart for month to date
def create_sales_chart(df, date):
    month = pd.Timestamp(date).to_pydatetime()
    sales_mtd = df[(df['month'] == month.month) & (df['year'] == month.year)]['total'].sum()
    sales_mtd_formatted = "{:,.2f}".format(sales_mtd)
    sales_mtd_last_year = df[(df['month'] == month.month) & (df['year'] == month.year - 1)]['total'].sum()
    sales_mtd_two_year = df[(df['month'] == month.month) & (df['year'] == month.year - 2)]['total'].sum()
    percent_vs_last_year_month = round(sales_mtd/sales_mtd_last_year*100,2)
    percent_vs_two_year_month = round(sales_mtd/sales_mtd_two_year*100,2)

    labels = ['vs 2Y ago', 'vs last year','MtD']
    category_names = [sales_mtd_two_year, sales_mtd_last_year, sales_mtd_formatted]

    trace = go.Bar(
        x=category_names,
        y=labels,
        orientation='h',
        text=category_names,
        textposition='auto',
        marker=dict(
            color='deepskyblue'
        )
    )

    data = [trace]
    layout = go.Layout(
        #xaxis=dict(title='Total Sales'),
        #yaxis=dict(title='Category'),
        margin=dict(l=1)
    )

    fig = go.Figure(data=data, layout=layout)
    return fig

@app.callback(
    Output('sales-chart', 'figure'),
    [Input('date-picker', 'date')],
    [State('local', 'data')]
)
def update_sales_chart(date, data):
    # Load the data based on whether the histo file exists or not
    if load_histo() is None:
        df = load_cached_data()
    else:
        df = load_histo()
    sales_chart = create_sales_chart(df, date)
    return sales_chart

# list of customers that did not create an order since...
def get_customers_to_chase(df):
    # Filter for customers who last ordered this year
    current_year = datetime.now().year
    df.name_o.dropna()
    # How long have we got each cust
    customer_length = df.groupby('name_o').agg({'sales_order_id': 'nunique', 'created_at': ['min', 'max']})
    customer_length['longevity'] = customer_length['created_at']['max'] - customer_length['created_at']['min']
    customer_length = customer_length.reset_index()
    customer_length.columns = ['name_o', 'orders_count', 'first_order', 'last_order', 'longevity']
    customer_length['last_order'] = pd.to_datetime(customer_length['last_order'], format='%Y-%m-%d')
    filtered_df = customer_length.loc[(customer_length['last_order'].dt.year == current_year)]
    sorted_df = filtered_df[['name_o', 'orders_count', 'last_order', 'longevity']].sort_values('last_order').head(10)
    # Format the longevity column in years and months
    sorted_df['longevity'] = sorted_df['longevity'].apply(lambda x: f'{int(x.days/365)}y {int((x.days%365)/30)}m')
    sorted_df['last_order'] = pd.to_datetime(sorted_df['last_order'], format='%Y-%m-%d').dt.strftime('%d-%m-%Y')

    table = go.Figure(data=[go.Table(
        columnwidth=1,
        header=dict(values=list(sorted_df.columns),
                    fill_color='lightgray',
                    align=['left', 'center']),
        cells=dict(values=[sorted_df.name_o, sorted_df.orders_count, sorted_df.last_order, sorted_df.longevity],
                   fill_color='white',
                   align=['left', 'center']))
    ])

    return table

@app.callback(
    Output('table', 'figure'),
    Input('local', 'data')
)
def update_table(data):
    df = load_cached_data()
    table = get_customers_to_chase(df)
    return table.to_dict() 

current_year = datetime.now().year

# Sales dashboard
sales_tab_content = dbc.Container([
     dbc.Row([
        dbc.Col(html.H6('... discover below ...', className='card-title mb-4')),
        html.Label('Select year:'),
        dcc.Dropdown(
            id='year-dropdown',
            clearable=False,
            searchable=False,
            placeholder='Select a year',
            #options=[],
            options=[{'label': year, 'value': year} for year in range(2019, 2024)],
            value=current_year,
        ),
        ], justify="center", align="center", className='mb-4'),

    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("Sales by Top 3 Customers")),
                dbc.CardBody(
                    [
                        dcc.Graph(id='sales-top-3-cust')
                    ], 
                    style={'height': '100%', 'display': 'flex', 'flex-direction': 'column'}
                ),
            ], 
            style={'height': '100%'}
            )
        ], md=6),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("Average Order Value")),
                dbc.CardBody(
                    [
                        dcc.Graph(id='avg-order-value')
                    ],
                    style={'height': '100%', 'display': 'flex', 'flex-direction': 'column'}
                ),
            ], 
            style={'height': '100%'}
            )
        ], md=6),
    ]),
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("Sales by Region")),
                dbc.CardBody(
                    [
                        dcc.Graph(id='sales-map')
                    ],
                    style={'height': '100%', 'display': 'flex', 'flex-direction': 'column'}
                ),
            ], 
            style={'height': '100%'}
            )
        ], md=6),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("Sales vs Order vs Total SKU")),
                dbc.CardBody(
                    [
                        dcc.Graph(id='sales-order-sku')
                    ],
                    style={'height': '100%', 'display': 'flex', 'flex-direction': 'column'}
                ),
            ], 
            style={'height': '100%'}
            )
        ], md=6),
    ]),
], fluid=True, style={'padding': '2rem'})

@app.callback(
    Output('sales-top-3-cust', 'figure'),
    [Input('year-dropdown', 'value')],
    [State('local', 'data')],
    prevent_initial_callback=True
)
def update_sales_graph_1(selected_year, data):
    # Load the data based on whether the histo file exists or not
    df = load_cached_data() if selected_year == current_year else load_histo()

    # Filter the data by the selected year
    filtered_df = df[df['year'] == selected_year]

    # Calculate total sales by month and customer
    sales_by_month_customer = filtered_df.groupby(['month', 'name_o'])['total'].sum().reset_index()

    # Find top customers for each month
    total_sales_by_customer = df.groupby('name_o')['total'].sum()
    top_customers = total_sales_by_customer.nlargest(20).index.tolist()
    customer_colors = {customer: px.colors.qualitative.Pastel1[i % len(px.colors.qualitative.Pastel1)]
                   for i, customer in enumerate(top_customers)}
    customer_colors['others'] = 'gray'
    def assign_color(customer):
        if customer in customer_colors:
            return customer_colors[customer]
        else:
            return 'gray'
    top_customers_by_month = sales_by_month_customer.groupby('month').apply(lambda x: x.nlargest(3, 'total')).reset_index(drop=True)

    # Group the remaining customers as "others"
    remaining_customers_by_month = sales_by_month_customer[~sales_by_month_customer['name_o'].isin(top_customers)]
    remaining_customers_by_month = remaining_customers_by_month.groupby('month').sum().reset_index()
    remaining_customers_by_month['name_o'] = 'others'

    # Concatenate the top customers and the "others" dataframes
    sales_by_month_customer = pd.concat([top_customers_by_month, remaining_customers_by_month])

    # Assign colors to each customer using the color mapping dictionary
    sales_by_month_customer['color'] = sales_by_month_customer['name_o'].apply(assign_color)

    # Create stacked bar chart of sales by customer
    fig = px.bar(sales_by_month_customer, x='month', y='total', color='name_o', color_discrete_map=customer_colors)
    fig.update_layout(
        title=f'Top 3 customers and others by month ({selected_year})',
        xaxis_title='Month',
        yaxis_title='Total Sales ($)',
        barmode='stack'
    )
    return fig

@app.callback(
    Output('avg-order-value', 'figure'),
    [Input('year-dropdown', 'value')],
    [State('local','data')],
    prevent_initial_callback=True
)
def update_avg_order_value(selected_year, data):
    # Load the data based on whether the histo file exists or not
    df = load_cached_data() if selected_year == current_year else load_histo()

    # Filter the data by the selected year
    filtered_df = df[df['year'] == selected_year]

    # Calculate the number of orders, total order value, and average order value by client
    # Calculate the number of orders, total order value, and average order value by client
    avg_order_value_by_client = filtered_df.groupby(['name_o']).agg({'total': 'sum', 'sales_order_id': 'nunique'})
    avg_order_value_by_client['avg_order_value'] = avg_order_value_by_client['total'] / avg_order_value_by_client['sales_order_id']

    # Calculate the number of items per basket by client
    items_per_basket_by_client = filtered_df.groupby(['name_o', 'sales_order_id'])['sku'].nunique().reset_index().groupby(['name_o'])['sku'].mean().reset_index()
    items_per_basket_by_client = items_per_basket_by_client.rename(columns={'sku': 'items_per_basket'})

    # Calculate the average item face price sold by client
    avg_item_face_price_by_client = filtered_df.groupby(['name_o'])['face_price'].mean().reset_index()

    # Merge all the dataframes together
    merged_df = pd.merge(avg_order_value_by_client, items_per_basket_by_client, on='name_o')
    merged_df = pd.merge(merged_df, avg_item_face_price_by_client, on='name_o')

    # Create the figure
    fig = px.scatter(merged_df, x='avg_order_value', y='items_per_basket', size='face_price', color='name_o', hover_name='name_o')
    fig.update_layout(
        title=f'Average Order Value and Items per Basket by Client ({selected_year})',
        xaxis_title='Average Order Value ($)',
        yaxis_title='Items per Basket',
    )
    return fig

@app.callback(
    Output('sales-map', 'figure'),
    [Input('year-dropdown', 'value')],
    [State('local', 'data')],
    prevent_initial_callback=True
)
def update_sales_map(selected_year, data):
    # Load the data based on whether the histo file exists or not
    df = load_cached_data() if selected_year == current_year else load_histo()

    # Filter the data by the selected year
    filtered_df = df[df['year'] == selected_year]

    # Perform country code mapping to country names
    sales_by_region = filtered_df.groupby(['country_o']).agg({'total': 'sum'}).reset_index()
    #sales_by_region['country_iso_alpha3'] = sales_by_region['country_o'].apply(lambda code: pycountry.countries.get(alpha_2=code).alpha_3)
    sales_by_region['country_iso_alpha3'] = sales_by_region['country_o'].apply(lambda code: pycountry.countries.get(alpha_2=code).alpha_3 if pycountry.countries.get(alpha_2=code) else None)

    fig = px.choropleth(sales_by_region, locations='country_iso_alpha3', color='total',
                        projection='natural earth')
    fig.update_layout(title=f'Total Sales by Region ({selected_year})')
    return fig

@app.callback(
    Output('sales-order-sku', 'figure'),
    [Input('year-dropdown', 'value')],
    [State('local','data')],
    #prevent_initial_callback=True
)
def update_sales_graph_2(selected_year,data):
    # Load the data based on whether the histo file exists or not
    df = load_cached_data() if selected_year == current_year else load_histo()

    filtered_df = df[df['year'] == selected_year]
    # Total Sales trend by month
    sales_by_month = filtered_df.groupby(pd.Grouper(key='date', freq='M')).sum()['total']
    #sales_by_month = filtered_df.groupby(filtered_df['date'].dt.to_period('M'))['total'].sum()
    sales_trace = go.Scatter(x=sales_by_month.index, y=sales_by_month.values, mode='lines', name='Total Sales')

    # Total Unique Orders trend by month
    unique_orders_by_month = filtered_df.groupby(pd.Grouper(key='date', freq='M'))['id'].nunique()
    #unique_orders_by_month = filtered_df.groupby(filtered_df['date'].dt.to_period('M'))['id'].nunique()
    unique_orders_trace = go.Scatter(x=unique_orders_by_month.index, y=unique_orders_by_month.values, mode='lines', name='Total Unique Orders')

    # Total SKU trend by month
    total_sku_by_month = filtered_df.groupby(pd.Grouper(key='date', freq='M'))['quantity'].sum()
    #total_sku_by_month = filtered_df.groupby(filtered_df['date'].dt.to_period('M'))['quantity'].sum()
    total_sku_trace = go.Scatter(x=total_sku_by_month.index, y=total_sku_by_month.values, mode='lines', name='Total SKUs')
    
    fig = go.Figure()
    
    fig.add_trace(sales_trace)
    fig.add_trace(unique_orders_trace)
    fig.add_trace(total_sku_trace)

    fig.update_layout(
        font=dict(size=10),
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis_title='Month',
        yaxis_title='Total',
        title="Sales, Unique Orders, and SKUs Trend"
    )
    return fig

@app.callback(
    Output('client-dropdown', 'options'),
    Input('local', 'data')
)
def update_client_dropdown_options(data):
    df = load_cached_data()  # Assuming this function loads the data from cache
    if df is not None:
        unique_names = df['name_o'].dropna().unique()
        unique_names_sorted = sorted(unique_names)
        options = [{'label': name, 'value': name} for name in unique_names_sorted]
        return options
    return []

# Create the second tab content for clients
clients_tab_content = dbc.Container([
     dbc.Row([
        dbc.Col(html.H6('... it will be filled with insights on phase 2 ...', className='card-title mb-4')),
        html.Label('Pick a name:'),
        dcc.Dropdown(
            id='client-dropdown',
            clearable=False,
            searchable=False,
            placeholder='Pick a client',
            #options=[],
        ),
        ], justify="center", align="center", className='mb-4'),
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("Client Favourite SKU (Top 3)")),
                dbc.CardBody(
                    [
                        #dcc.Graph(id='client-favourite-sku-graph')
                    ], 
                    style={'height': '100%', 'display': 'flex', 'flex-direction': 'column'}
                ),
            ], 
            style={'height': '100%'}
            )
        ], md=6),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("SKU Bundled Together")),
                dbc.CardBody(
                    [
                        #dcc.Graph(id='sku-bundled-output')
                    ], 
                    style={'height': '100%', 'display': 'flex', 'flex-direction': 'column'}
                ),
            ], 
            style={'height': '100%'}
            )
        ], md=6),
    ]),
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("Client Periodicity of Order")),
                dbc.CardBody(
                    [
                        #dcc.Graph(id='client-periodicity-graph')
                    ], 
                    style={'height': '100%', 'display': 'flex', 'flex-direction': 'column'}
                ),
            ], 
            style={'height': '100%'}
            )
        ], md=6),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("Orders per Customer by Year")),
                dbc.CardBody(
                    [
                        #dcc.Graph(id='orders-per-customer-heatmap')
                    ], 
                    style={'height': '100%', 'display': 'flex', 'flex-direction': 'column'}
                ),
            ], 
            style={'height': '100%'}
            )
        ], md=6),
    ]),
], fluid=True, style={'padding': '2rem'})

prospects_tab_content = dbc.Container([
    dbc.Row(
        dbc.Col(html.H6('... it will be filled with insights on phase 2 ...', className='card-title mb-4'),
                #width={'size': 6, 'offset': 3}
               ),
        justify="center",
        align="center",
        className='mb-4'
    ),
    dbc.Row(
        dbc.Card(
            [
                dbc.CardHeader(html.H5("In a nutshell")),
                dbc.CardBody(
                    [
                        dcc.Graph(id='habits-graph')
                    ],
                    style={'height': '100%', 'display': 'flex', 'flex-direction': 'column', 'overflow-y': 'scroll'}
                ),
            ],
            className="w-100",
        ),
    ),
], fluid=True, style={'padding': '2rem'})

@app.callback(
    Output("habits-graph", "figure"),
    Input("local", "data")
)
def update_habits_graph(data):
    df = load_histo()
    customer_orders = df.groupby(['name_o', 'year', 'month', 'weekday']).agg({
            'sales_order_id': 'nunique',
            'date': ['min', 'max']
        })
    customer_orders = customer_orders.reset_index()
    customer_orders.columns = ['name_o', 'year', 'month', 'weekday', 'orders_count', 'first_order', 'last_order']

    years = customer_orders.groupby(['name_o', 'year']).agg({'orders_count': 'sum'})
    year_pivot = years.pivot_table(index='name_o', columns='year', values='orders_count')

    fig = go.Figure(data=go.Heatmap(
        z=year_pivot.values,
        x=year_pivot.columns,
        y=year_pivot.index,
        colorscale='Blues',
        colorbar=dict(title='Orders Count')
    ))

    fig.update_layout(
        title='Orders per Customer by Year',
        xaxis=dict(title='Year', tickangle=45),
        yaxis=dict(title='Customer'),
        height=3000,
        margin=dict(l=20, r=20, t=40, b=20)
    )

    return fig

# Define tabs
tabs = dbc.Tabs(
    [
        dbc.Tab(label="Historic Sales", children=sales_tab_content),
        dbc.Tab(label="Customer Analysis", children=clients_tab_content),
        dbc.Tab(label="Prospects Market Research", children=prospects_tab_content),
    ],
    id="tabs",
    active_tab="Historic Sales",
)

# Define app layout
app.layout = html.Div([
    store, #dcc.Store(id='local', storage_type='local'),  # Move dcc.Store outside navbar
    navbar,
    html.Div(id='table-container'),
    page_layout,
    dbc.Container([
        dbc.Row([
            dbc.Col([
                tabs,
            ]),
        ], className='mt-4')
    ])
], style={'padding': '0rem 0rem 4rem 0rem'})

# Set the app layout
#app.layout = app_layout
if __name__ == '__main__':
    Timer(1, open_browser).start();
    app.run_server(debug=True, use_reloader=False, port=8090)
    #app.run_server(host='0.0.0.0', port=8090, debug=True)
