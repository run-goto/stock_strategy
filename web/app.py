import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import logging
from services.stock_service import update_stock_data, get_trade_days, stock_zh_a_hist
from apscheduler.schedulers.background import BackgroundScheduler

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 初始化Dash应用
app = dash.Dash(__name__,
                external_stylesheets=[dbc.themes.BOOTSTRAP],
                suppress_callback_exceptions=True)
server = app.server

# 定义应用布局
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("A股策略分析系统", className="text-center my-4"),
            html.Hr(),
        ], width=12)
    ]),

    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("策略参数设置"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("涨幅阈值 (%)"),
                            dbc.Input(id="threshold", type="number", value=9, min=0, max=20),
                        ], width=6),
                        dbc.Col([
                            dbc.Label("历史交易日数"),
                            dbc.Input(id="days", type="number", value=30, min=10, max=60),
                        ], width=6),
                    ]),
                    html.Div(className="mb-3"),
                    dbc.Button("开始分析", id="analyze-button", color="primary", className="w-100"),
                ])
            ], className="mb-4"),
        ], width=12)
    ]),

    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("分析结果"),
                dbc.CardBody([
                    html.Div(id="results-container"),
                ])
            ])
        ], width=12)
    ]),

    # 加载状态
    dcc.Loading(
        id="loading",
        type="default",
        children=html.Div(id="loading-output")
    ),

    # 存储数据
    dcc.Store(id='stock-data-store'),
], fluid=True)


@app.callback(
    [Output("stock-data-store", "data"),
     Output("loading-output", "children")],
    [Input("analyze-button", "n_clicks")],
    [State("threshold", "value"),
     State("days", "value")]
)
def update_stock_data_callback(n_clicks, days):
    """更新股票数据回调"""
    if n_clicks is None:
        return None, ""

    try:
        logger.info(f"开始分析: 天数={days}")
        result_stocks = update_stock_data(days)
        return result_stocks, ""

    except Exception as e:
        logger.error(f"分析过程中出错: {str(e)}")
        return None, f"发生错误: {str(e)}"


@app.callback(
    Output("results-container", "children"),
    [Input("stock-data-store", "data")]
)
def update_results(data):
    """更新结果显示"""
    if not data:
        return html.Div("请点击'开始分析'按钮开始分析")

    # 按策略分组
    strategy_groups = {}
    for stock in data:
        strategy = stock['strategy']
        if strategy not in strategy_groups:
            strategy_groups[strategy] = []
        strategy_groups[strategy].append(stock)

    # 创建结果展示
    results = []
    for strategy, stocks in strategy_groups.items():
        strategy_div = html.Div([
            html.H3(f"{strategy} ({len(stocks)}只)"),
            html.Div([
                create_stock_card(stock) for stock in stocks
            ], style={'display': 'flex', 'flexWrap': 'wrap', 'justifyContent': 'center'})
        ])
        results.append(strategy_div)

    return html.Div(results)


def create_stock_card(stock):
    """创建股票信息卡片"""
    return html.Div([
        dbc.Card([
            dbc.CardHeader(f"{stock['name']}({stock['code']})"),
            dbc.CardBody([
                html.P(f"当前价格: {stock['current_price']:.2f}"),
                html.P(f"当前成交量: {stock['current_volume']:,.0f}"),
                dbc.Button('查看详情', id={'type': 'show-details', 'index': stock['code']},
                           color="primary", className="mt-2")
            ])
        ], className="mb-3", style={'width': '300px', 'margin': '10px'}),
        html.Div(id={'type': 'details', 'index': stock['code']})
    ])


@app.callback(
    Output({'type': 'details', 'index': dash.MATCH}, 'children'),
    [Input({'type': 'show-details', 'index': dash.MATCH}, 'n_clicks')],
    [State('days', 'value')]
)
def show_stock_details(n_clicks, days):
    """显示股票详细信息"""
    if n_clicks == 0:
        return None

    try:
        # 获取触发回调的股票代码
        ctx = dash.callback_context
        if not ctx.triggered:
            return None
        stock_code = ctx.triggered[0]['prop_id'].split('.')[0].split(':')[1].strip('{}"')

        # 获取股票数据
        start_date, end_date = get_trade_days(days)
        hist_data = stock_zh_a_hist(
            symbol=stock_code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"
        )

        if hist_data.empty:
            return html.Div("无法获取股票数据")

        # 创建K线图
        fig = go.Figure(data=[go.Candlestick(
            x=hist_data['日期'],
            open=hist_data['开盘'],
            high=hist_data['最高'],
            low=hist_data['最低'],
            close=hist_data['收盘']
        )])

        fig.update_layout(
            title=f"{stock_code} K线图",
            yaxis_title="价格",
            xaxis_title="日期",
            height=400
        )

        return html.Div([
            dcc.Graph(figure=fig),
            html.Div([
                html.H4("交易数据"),
                html.Table([
                    html.Thead(html.Tr([
                        html.Th("日期"), html.Th("开盘"), html.Th("最高"),
                        html.Th("最低"), html.Th("收盘"), html.Th("成交量"),
                        html.Th("涨跌幅")
                    ])),
                    html.Tbody([
                        html.Tr([
                            html.Td(row['日期']),
                            html.Td(f"{row['开盘']:.2f}"),
                            html.Td(f"{row['最高']:.2f}"),
                            html.Td(f"{row['最低']:.2f}"),
                            html.Td(f"{row['收盘']:.2f}"),
                            html.Td(f"{row['成交量']:,.0f}"),
                            html.Td(f"{row['涨跌幅']:.2f}%")
                        ]) for _, row in hist_data.iterrows()
                    ])
                ], style={'width': '100%', 'marginTop': '20px'})
            ])
        ])

    except Exception as e:
        logger.error(f"显示股票详情时出错: {str(e)}")
        return html.Div(f"显示详情出错: {str(e)}")


# 初始化调度器
scheduler = BackgroundScheduler()
# 每天早上9:30更新数据
scheduler.add_job(update_stock_data, 'cron', hour=9, minute=30)
scheduler.start()
