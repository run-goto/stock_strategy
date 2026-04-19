# 快速开始 - 《短线操盘实战技巧》策略

## 1分钟快速体验

### 步骤1: 启动服务
```bash
# 同时启动后端和前端
bash scripts/start_dev.sh

# 或分别启动
bash scripts/start_backend.sh
bash scripts/start_frontend.sh
```

### 步骤2: 查看可用策略
```bash
curl http://127.0.0.1:8001/api/v1/strategies
```

你会看到9个已启用的策略,包括6个《短线操盘实战技巧》核心策略。

### 步骤3: 运行策略扫描

#### 方式A: 使用curl
```bash
# 创建扫描任务
curl -X POST http://127.0.0.1:8001/api/v1/scans \
  -H "Content-Type: application/json" \
  -d '{"start": "20260401", "end": "20260412", "targets": ["20260412"]}'

# 假设返回 job_id: "abc123"
# 查询任务状态
curl http://127.0.0.1:8001/api/v1/scans/abc123

# 获取扫描结果
curl http://127.0.0.1:8001/api/v1/scans/abc123/results
```

#### 方式B: 使用Python脚本
```python
import requests

# 创建扫描任务
response = requests.post(
    'http://127.0.0.1:8001/api/v1/scans',
    json={
        'start': '20260401',
        'end': '20260412',
        'targets': ['20260412']
    }
)
job_id = response.json()['job_id']
print(f'任务ID: {job_id}')

# 等待任务完成(实际使用中需要轮询)
import time
time.sleep(10)

# 获取结果
results = requests.get(f'http://127.0.0.1:8001/api/v1/scans/{job_id}/results')
for item in results.json():
    print(f"{item['code']} - {item['strategy']}")
```

## 策略说明

### 📊 ST-01: 双均线趋势策略
**适合**: 趋势跟踪,中长期持有  
**信号**: 股价首次突破MA100且放量  
**特点**: 稳健,适合牛市

### 📈 ST-02: 低位123结构突破
**适合**: 底部反转,捕捉启动点  
**信号**: 识别123形态后突破高点2  
**特点**: 技术形态明确,成功率高

### 🔄 ST-03: MACD底背离双突破
**适合**: 超跌反弹  
**信号**: MACD底背离+双突破  
**特点**: 逆势操作,需轻仓

### ⚡ ST-04: 向上突破缺口追涨
**适合**: 强势突破行情  
**信号**: 跳空缺口突破阻力位  
**特点**: 爆发力强,速度快

### 🎯 ST-05: 缺口回踩支撑买入
**适合**: 突破后的二次买点  
**信号**: 缺口回踩确认支撑有效  
**特点**: 风险相对较低

### 🔥 ST-06: 强势涨停突破
**适合**: 短线追涨  
**信号**: 涨停板突破前高  
**特点**: 爆发力最强,风险也最高

## 配置调整

编辑 `backend/config/app_config.yaml` 启用/禁用策略:

```yaml
strategies:
  DualMATrendStrategy:
    enabled: true  # 改为false禁用
  Low123BreakoutStrategy:
    enabled: true
  # ... 其他策略
```

修改后重启服务即可生效。

## 常见问题

### Q1: 为什么有些策略没有信号?
A: 可能原因:
- 历史数据不足(不同策略需要不同天数)
- 当前市场不符合策略条件
- 策略参数需要调整

### Q2: 如何查看策略需要的最少数据天数?
A: 参考下表:

| 策略 | 最少天数 |
|------|---------|
| ST-01 | 101天 |
| ST-02 | 60天 |
| ST-03 | 80天 |
| ST-04 | 61天 |
| ST-05 | 40天 |
| ST-06 | 61天 |

### Q3: 如何提高扫描速度?
A: 在 `backend/config/app_config.yaml` 中调整:
```yaml
defaults:
  max_workers: 50  # 增加并发数
```

### Q4: 数据从哪里来?
A: 系统优先从本地DuckDB读取,缺失时自动从腾讯证券API补抓。

### Q5: 如何导出结果为CSV?
```python
import requests
import pandas as pd

response = requests.get('http://127.0.0.1:8001/api/v1/scans/{job_id}/results')
df = pd.DataFrame(response.json())
df.to_csv('strategy_results.csv', index=False, encoding='utf-8-sig')
```

## 下一步

1. 📖 阅读详细文档: `docs/ShortTermStrategies.md`
2. 🧪 运行测试: `python tests/test_short_term_strategies.py`
3. 📊 查看实现总结: `IMPLEMENTATION_SUMMARY.md`
4. 🔧 根据回测结果调整策略参数

## 技术支持

- 项目文档: `docs/PRD.md`, `docs/Strategies.md`
- 测试用例: `tests/` 目录
- API文档: 启动服务后访问 `http://127.0.0.1:8001/docs`

---

**祝交易顺利!** 🚀

