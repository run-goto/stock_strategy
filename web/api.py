# file: web/api.py
"""
A股策略分析系统 - REST API
提供前端所需的所有接口
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import logging
from datetime import datetime
import threading
import uuid

from services.db_service import (
    get_all_stocks, get_stock_count, get_stock_loaded_dates,
    get_daily_data, get_all_loaded_dates, get_date_stock_count,
    get_daily_data_range
)
from services.sync_service import (
    sync_stock_list, sync_stock_daily_data, 
    sync_all_stocks_daily_data, sync_today_daily_data
)
from services.strategy_loader import load_strategies_from_config

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 创建 Flask 应用
app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 后台任务状态存储
background_tasks = {}


def run_in_background(task_id, func, *args, **kwargs):
    """在后台线程中运行任务"""
    def wrapper():
        try:
            background_tasks[task_id]['status'] = 'running'
            result = func(*args, **kwargs)
            background_tasks[task_id]['status'] = 'completed'
            background_tasks[task_id]['result'] = result
        except Exception as e:
            background_tasks[task_id]['status'] = 'failed'
            background_tasks[task_id]['error'] = str(e)
            logger.error(f"后台任务 {task_id} 失败: {str(e)}")
    
    thread = threading.Thread(target=wrapper, daemon=True)
    thread.start()
    return thread


# ==================== 股票信息 API ====================

@app.route('/api/stocks', methods=['GET'])
def api_get_stocks():
    """获取股票列表"""
    search = request.args.get('search', '')
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    stocks = get_all_stocks(search=search if search else None, limit=limit, offset=offset)
    total = get_stock_count()
    
    return jsonify({
        'success': True,
        'data': stocks,
        'total': total
    })


@app.route('/api/stocks/sync', methods=['POST'])
def api_sync_stocks():
    """同步股票列表"""
    result = sync_stock_list()
    return jsonify(result)


@app.route('/api/stocks/count', methods=['GET'])
def api_stock_count():
    """获取股票总数"""
    count = get_stock_count()
    return jsonify({'success': True, 'count': count})


# ==================== 行情数据 API ====================

@app.route('/api/daily/<code>/dates', methods=['GET'])
def api_get_loaded_dates(code):
    """获取某只股票已加载的交易日期"""
    dates = get_stock_loaded_dates(code)
    return jsonify({
        'success': True,
        'code': code,
        'dates': dates,
        'count': len(dates)
    })


@app.route('/api/daily/<code>/<trade_date>', methods=['GET'])
def api_get_daily_data(code, trade_date):
    """获取某只股票某天的行情数据"""
    data = get_daily_data(code, trade_date)
    if data:
        return jsonify({'success': True, 'data': data})
    else:
        return jsonify({'success': False, 'message': '数据不存在'}), 404


@app.route('/api/daily/<code>/range', methods=['GET'])
def api_get_daily_range(code):
    """获取某只股票日期范围内的行情数据"""
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    
    if not start_date or not end_date:
        return jsonify({'success': False, 'message': '请提供开始和结束日期'}), 400
    
    data = get_daily_data_range(code, start_date, end_date)
    return jsonify({
        'success': True,
        'code': code,
        'data': data,
        'count': len(data)
    })


@app.route('/api/daily/sync', methods=['POST'])
def api_sync_daily():
    """同步单只股票的行情数据"""
    data = request.get_json()
    code = data.get('code')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    
    if not code or not start_date or not end_date:
        return jsonify({'success': False, 'message': '请提供股票代码和日期范围'}), 400
    
    result = sync_stock_daily_data(code, start_date, end_date)
    return jsonify(result)


@app.route('/api/daily/sync-batch', methods=['POST'])
def api_sync_batch():
    """批量同步所有股票的行情数据 - 后台执行"""
    data = request.get_json()
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    
    if not start_date or not end_date:
        return jsonify({'success': False, 'message': '请提供日期范围'}), 400
    
    # 创建后台任务
    task_id = str(uuid.uuid4())
    background_tasks[task_id] = {
        'status': 'pending',
        'type': 'sync_batch',
        'start_time': datetime.now().isoformat()
    }
    
    run_in_background(task_id, sync_all_stocks_daily_data, start_date, end_date)
    
    return jsonify({
        'success': True,
        'message': f'后台任务已启动，正在同步 {start_date} 至 {end_date} 的数据...',
        'task_id': task_id
    })


@app.route('/api/daily/sync-today', methods=['POST'])
def api_sync_today():
    """同步当天所有股票的交易数据 - 后台执行"""
    # 创建后台任务
    task_id = str(uuid.uuid4())
    background_tasks[task_id] = {
        'status': 'pending',
        'type': 'sync_today',
        'start_time': datetime.now().isoformat()
    }
    
    run_in_background(task_id, sync_today_daily_data)
    
    return jsonify({
        'success': True,
        'message': '后台任务已启动，正在同步当天交易数据...',
        'task_id': task_id
    })


@app.route('/api/tasks/<task_id>', methods=['GET'])
def api_task_status(task_id):
    """获取后台任务状态"""
    if task_id not in background_tasks:
        return jsonify({'success': False, 'message': '任务不存在'}), 404
    
    task = background_tasks[task_id]
    return jsonify({
        'success': True,
        'task_id': task_id,
        'status': task.get('status'),
        'result': task.get('result'),
        'error': task.get('error'),
        'start_time': task.get('start_time')
    })


@app.route('/api/daily/loaded-dates', methods=['GET'])
def api_all_loaded_dates():
    """获取所有已加载的交易日期"""
    dates = get_all_loaded_dates()
    return jsonify({
        'success': True,
        'dates': dates,
        'count': len(dates)
    })


@app.route('/api/sync-logs', methods=['GET'])
def api_sync_logs():
    """获取同步日志"""
    from services.db_service import get_recent_sync_logs, get_today_loaded_stock_count
    
    limit = request.args.get('limit', 30, type=int)
    logs = get_recent_sync_logs(limit)
    
    # 添加今日实时统计
    today = datetime.now().strftime('%Y%m%d')
    today_loaded = get_today_loaded_stock_count(today)
    total_stocks = get_stock_count()
    
    return jsonify({
        'success': True,
        'data': logs,
        'today_stats': {
            'date': today,
            'loaded': today_loaded,
            'total': total_stocks,
            'completion_rate': round(today_loaded / total_stocks * 100, 1) if total_stocks > 0 else 0
        }
    })


# ==================== 策略分析 API ====================

@app.route('/api/strategies', methods=['GET'])
def api_get_strategies():
    """获取可用策略列表"""
    strategies = load_strategies_from_config()
    strategy_list = [
        {'name': s.name, 'value': s.__class__.__name__}
        for s in strategies
    ]
    return jsonify({
        'success': True,
        'data': strategy_list
    })


@app.route('/api/strategies/analyze', methods=['POST'])
def api_analyze():
    """执行策略分析 - 使用数据库中已同步的数据"""
    data = request.get_json()
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    selected_strategies = data.get('strategies', [])
    
    if not start_date or not end_date:
        return jsonify({'success': False, 'message': '请提供日期范围'}), 400
    
    if not selected_strategies:
        return jsonify({'success': False, 'message': '请选择至少一个策略'}), 400
    
    try:
        import pandas as pd
        from services.strategy_loader import load_strategies_from_config
        
        # 加载策略
        all_strategies = load_strategies_from_config()
        strategies_to_use = [s for s in all_strategies if s.__class__.__name__ in selected_strategies]
        
        if not strategies_to_use:
            return jsonify({'success': False, 'message': '未找到选择的策略'}), 400
        
        # 获取所有股票
        stocks = get_all_stocks(limit=10000)
        logger.info(f"开始策略分析: {len(stocks)} 只股票, {len(strategies_to_use)} 个策略")
        
        results = []
        processed = 0
        
        for stock in stocks:
            code = stock['code']
            name = stock['name']
            
            # 从数据库获取行情数据
            daily_data = get_daily_data_range(code, start_date, end_date)
            
            if not daily_data or len(daily_data) < 5:
                continue
            
            # 转换为 DataFrame
            df = pd.DataFrame(daily_data)
            df['date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
            df = df.sort_values('date').reset_index(drop=True)
            
            # 对每个策略进行检查
            for strategy in strategies_to_use:
                try:
                    if strategy.check(df):
                        results.append({
                            'code': code,
                            'name': name,
                            'strategy': strategy.name,
                            'target_date': end_date,
                            'current_price': df.iloc[-1].get('close')
                        })
                except Exception as e:
                    logger.warning(f"策略 {strategy.name} 检查 {code} 失败: {str(e)}")
            
            processed += 1
            if processed % 500 == 0:
                logger.info(f"策略分析进度: {processed}/{len(stocks)}")
        
        logger.info(f"策略分析完成，分析了 {processed} 只股票，共找到 {len(results)} 条符合条件的记录")
        
        # 按策略分组
        strategy_groups = {}
        for r in results:
            strategy = r['strategy']
            if strategy not in strategy_groups:
                strategy_groups[strategy] = []
            strategy_groups[strategy].append(r)
        
        return jsonify({
            'success': True,
            'data': strategy_groups,
            'total': len(results),
            'analyzed': processed,
            'message': f'分析了 {processed} 只有效股票，找到 {len(results)} 只符合条件'
        })
        
    except Exception as e:
        logger.error(f"策略分析失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


# ==================== 数据导出 API ====================

@app.route('/api/strategies/export', methods=['POST'])
def api_export_results():
    """导出策略分析结果为CSV"""
    import io
    import csv
    from flask import Response
    
    data = request.get_json()
    results = data.get('results', {})
    
    if not results:
        return jsonify({'success': False, 'message': '没有可导出的数据'}), 400
    
    # 创建CSV内容
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 写入表头
    writer.writerow(['股票代码', '股票名称', '策略名称', '目标日期', '当前价格'])
    
    # 写入数据
    for strategy_name, stocks in results.items():
        for stock in stocks:
            writer.writerow([
                stock.get('code', ''),
                stock.get('name', ''),
                stock.get('strategy', strategy_name),
                stock.get('target_date', ''),
                stock.get('current_price', '')
            ])
    
    # 生成文件名
    filename = f"strategy_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    # 返回CSV文件
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename={filename}',
            'Content-Type': 'text/csv; charset=utf-8-sig'
        }
    )


# ==================== 健康检查 ====================

@app.route('/api/health', methods=['GET'])
def api_health():
    """健康检查"""
    return jsonify({
        'success': True,
        'message': 'API is running',
        'timestamp': datetime.now().isoformat()
    })


# ==================== 启动应用 ====================

if __name__ == '__main__':
    # 启动定时任务调度器
    from services.scheduler_service import start_scheduler_thread
    start_scheduler_thread()
    
    # 启动 Flask 应用
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)

