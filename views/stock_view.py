import dash
from dash import html, dcc, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import logging
from services.stock_service import update_stock_data, get_trade_days, stock_zh_a_hist
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_stock_view():
    """创建股票分析页面"""
    app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
    
    # 定义策略选项
    strategy_options = [
        {"label": "连续两天上涨", "value": "ContinuousRiseStrategy"},
        {"label": "三只小阳线", "value": "ThreeSmallRiseStrategy"},
        {"label": "全部策略", "value": "all"}
    ]
    
    app.layout = dbc.Container([
        dbc.Row([
            dbc.Col([
                html.H1("股票策略分析系统", className="text-center my-4"),
                html.Hr(),
            ], width=12)
        ]),
        
        # 策略选择区域
        dbc.Row([
            dbc.Col([
                html.H4("选择分析策略", className="mb-3"),
                dcc.Dropdown(
                    id='strategy-selector',
                    options=strategy_options,
                    value='all',
                    clearable=False,
                    className="mb-3"
                ),
            ], width=12)
        ]),
        
        # 参数设置区域
        dbc.Row([
            dbc.Col([
                html.H4("策略参数设置", className="mb-3"),
                dbc.InputGroup([
                    dbc.InputGroupText("涨幅阈值(%)"),
                    dbc.Input(
                        id="threshold-input",
                        type="number",
                        value=9,
                        min=0,
                        max=100,
                        step=0.1
                    ),
                ], className="mb-3"),
                
                dbc.InputGroup([
                    dbc.InputGroupText("历史天数"),
                    dbc.Input(
                        id="days-input",
                        type="number",
                        value=30,
                        min=1,
                        max=365,
                        step=1
                    ),
                ], className="mb-3"),
                
                dbc.Button(
                    "开始分析",
                    id="analyze-button",
                    color="primary",
                    className="w-100"
                ),
            ], width=12, md=6),
            
            # 结果统计区域
            dbc.Col([
                html.H4("分析结果统计", className="mb-3"),
                html.Div(id="stats-container", className="p-3 border rounded"),
            ], width=12, md=6),
        ]),
        
        # 加载状态
        dcc.Loading(
            id="loading",
            type="default",
            children=html.Div(id="loading-output")
        ),
        
        # 结果展示区域
        dbc.Row([
            dbc.Col([
                html.H4("符合条件的股票", className="mb-3"),
                html.Div(id="results-container"),
            ], width=12)
        ]),
        
        # 存储数据
        dcc.Store(id='stock-data-store'),
        
        # 模态框用于显示股票详情
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("股票详情")),
            dbc.ModalBody([
                dcc.Graph(id="stock-detail-chart"),
                html.Div(id="stock-detail-info")
            ]),
            dbc.ModalFooter(
                dbc.Button("关闭", id="close-modal", className="ms-auto", n_clicks=0)
            ),
        ], id="stock-detail-modal", size="lg", is_open=False),
    ], fluid=True)
    
    return app

def register_callbacks(app):
    """注册回调函数"""
    
    @app.callback(
        [Output('stock-data-store', 'data'),
         Output('loading-output', 'children')],
        [Input('analyze-button', 'n_clicks')],
        [State('threshold-input', 'value'),
         State('days-input', 'value')]
    )
    def update_stock_data_callback(n_clicks, threshold, days):
        if n_clicks is None:
            return None, ""
            
        try:
            logger.info(f"开始分析，阈值: {threshold}%, 天数: {days}")
            result_stocks = update_stock_data(threshold, days)
            if result_stocks:
                return result_stocks, ""
            return None, "未找到符合条件的股票"
        except Exception as e:
            logger.error(f"分析出错: {str(e)}")
            return None, f"分析出错: {str(e)}"
    
    @app.callback(
        [Output('results-container', 'children'),
         Output('stats-container', 'children')],
        [Input('stock-data-store', 'data'),
         Input('strategy-selector', 'value')]
    )
    def update_results(data, selected_strategy):
        if not data:
            return [], []
            
        # 按策略分组
        strategy_groups = {}
        for stock in data:
            strategy = stock['strategy']
            if strategy not in strategy_groups:
                strategy_groups[strategy] = []
            strategy_groups[strategy].append(stock)
            
        # 统计信息
        stats = []
        for strategy, stocks in strategy_groups.items():
            stats.append(html.P(f"{strategy}: {len(stocks)} 只股票"))
            
        # 根据选择的策略过滤股票
        if selected_strategy != 'all':
            filtered_stocks = [s for s in data if s['strategy'] == selected_strategy]
        else:
            filtered_stocks = data
            
        # 创建股票卡片
        stock_cards = []
        for stock in filtered_stocks:
            card = create_stock_card(stock)
            stock_cards.append(card)
            
        return stock_cards, stats
    
    @app.callback(
        [Output('stock-detail-modal', 'is_open'),
         Output('stock-detail-chart', 'figure'),
         Output('stock-detail-info', 'children')],
        [Input('show-details-button', 'n_clicks'),
         Input('close-modal', 'n_clicks')],
        [State('stock-data-store', 'data'),
         State('days-input', 'value')]
    )
    def show_stock_details(show_clicks, close_clicks, data, days):
        if not data or not show_clicks:
            return False, {}, ""
            
        ctx = callback_context
        if not ctx.triggered:
            return False, {}, ""
            
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        if button_id == 'close-modal':
            return False, {}, ""
            
        # 获取股票代码
        stock_code = ctx.triggered[0]['prop_id'].split('.')[0].split('-')[1]
        stock = next((s for s in data if s['code'] == stock_code), None)
        if not stock:
            return False, {}, ""
            
        # 获取历史数据
        start_date, end_date = get_trade_days(days)
        hist_data = stock_zh_a_hist(
            symbol=stock_code,
            period="daily",
            adjust="qfq",
            start_date=start_date,
            end_date=end_date
        )
        
        if hist_data.empty:
            return True, {}, "无法获取历史数据"
            
        # 创建K线图
        fig = go.Figure(data=[go.Candlestick(
            x=hist_data['日期'],
            open=hist_data['开盘'],
            high=hist_data['最高'],
            low=hist_data['最低'],
            close=hist_data['收盘']
        )])
        
        fig.update_layout(
            title=f"{stock['name']}({stock_code}) 历史走势",
            yaxis_title="价格",
            xaxis_title="日期"
        )
        
        # 创建详细信息
        info = [
            html.P(f"策略: {stock['strategy']}"),
            html.P(f"当前价格: {stock['current_price']}"),
            html.P(f"成交量: {stock['volume']}"),
            html.P(f"涨幅: {stock['increase']}%")
        ]
        
        return True, fig, info

def create_stock_card(stock):
    """创建单个股票信息卡片"""
    return dbc.Card([
        dbc.CardBody([
            html.H4(f"{stock['name']}({stock['code']})", className="card-title"),
            html.P(f"策略: {stock['strategy']}", className="card-text"),
            html.P(f"当前价格: {stock['current_price']}", className="card-text"),
            html.P(f"成交量: {stock['volume']}", className="card-text"),
            html.P(f"涨幅: {stock['increase']}%", className="card-text"),
            dbc.Button(
                "查看详情",
                id=f"show-details-button-{stock['code']}",
                color="primary",
                className="mt-2"
            )
        ])
    ], className="mb-3") 