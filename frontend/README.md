# 前端使用说明

## 📁 项目结构

```
frontend/
├── index.html              # 主页面
└── static/
    ├── css/
    │   └── style.css      # 样式文件
    └── js/
        └── app.js         # JavaScript逻辑
```

## 🚀 快速启动

### 方式1: 使用Python内置服务器 (推荐)

```bash
# 在项目根目录运行
python start_frontend.py
```

然后在浏览器访问: http://localhost:8080

### 方式2: 直接打开HTML文件

直接在浏览器中打开 `frontend/index.html` 文件即可。

> **注意**: 某些浏览器可能限制本地文件的JavaScript功能,建议使用方式1。

### 方式3: 使用其他静态服务器

```bash
# 使用Node.js的http-server
npx http-server frontend -p 8080

# 使用Python 3
cd frontend
python -m http.server 8080
```

## ✨ 功能特性

### 1. 策略回测页面

- **参数配置**: 选择股票、策略、日期范围、初始资金等
- **性能指标**: 实时显示收益率、夏普比率、最大回撤等
- **资金曲线**: Chart.js绘制的交互式资金曲线图
- **详细数据**: 完整的回测数据统计

### 2. 回测结果页面

- **历史记录**: 自动保存所有回测记录
- **数据表格**: 清晰展示每次回测的关键指标
- **快速查看**: 一键查看历史回测详情

### 3. 参数优化页面

- **网格搜索**: 自动寻找最优参数组合
- **结果排序**: 按收益率降序排列
- **Top N展示**: 显示表现最好的参数组合

## 🎨 界面预览

### 主要功能模块

1. **导航栏**
   - 策略回测
   - 回测结果
   - 参数优化

2. **性能指标卡片**
   - 总收益率
   - 年化收益
   - 夏普比率
   - 最大回撤
   - 交易次数
   - 胜率

3. **可视化图表**
   - 资金曲线图 (Chart.js)
   - 支持缩放和悬停查看

4. **数据表格**
   - 回测详情
   - 历史记录列表

## 🔧 技术栈

- **HTML5**: 语义化标签
- **CSS3**: 
  - Flexbox/Grid布局
  - CSS变量
  - 响应式设计
  - 渐变和动画
- **JavaScript (ES6+)**:
  - 异步/await
  - 模块化代码
  - LocalStorage持久化
- **Chart.js 4.x**: 数据可视化

## 📱 响应式设计

前端页面完全响应式,支持:
- 🖥️ 桌面端 (1200px+)
- 💻 平板端 (768px - 1200px)
- 📱 移动端 (< 768px)

## 🎯 当前状态

### ✅ 已完成
- [x] 页面布局和样式
- [x] 表单交互
- [x] 数据可视化
- [x] 历史记录管理
- [x] 模拟数据演示

### 🔄 待完成
- [ ] 后端API集成
- [ ] 真实回测数据展示
- [ ] 批量回测功能
- [ ] 参数优化功能
- [ ] 导出报告功能

## 🔌 API集成

目前前端仍使用模拟数据进行演示。后端 v2 已提供真实回测任务 API，前端接入仍是后续工作。

1. **实现后端API端点** (参考 `api/routes.py`)

```python
@app.post("/api/v1/backtests")
async def create_backtest(params: BacktestRequest):
    # 创建异步回测任务，随后通过 /api/v1/backtests/{job_id}/results 查询结果
    ...
```

2. **修改前端API调用** (在 `app.js` 中)

```javascript
// 取消注释并修改 callBacktestAPI 函数
const response = await fetch(`${API_BASE_URL}/backtests`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
});
```

## 🎨 自定义样式

修改 `static/css/style.css` 中的CSS变量即可快速调整主题:

```css
:root {
    --primary-color: #1890ff;      /* 主色调 */
    --success-color: #52c41a;      /* 成功色 */
    --danger-color: #ff4d4f;       /* 危险色 */
    --bg-color: #f5f5f5;           /* 背景色 */
}
```

## 📊 Chart.js配置

资金曲线图的配置在 `app.js` 的 `drawEquityChart()` 函数中:

```javascript
equityChart = new Chart(ctx, {
    type: 'line',
    data: { ... },
    options: {
        responsive: true,
        plugins: { ... },
        scales: { ... }
    }
});
```

参考 [Chart.js文档](https://www.chartjs.org/docs/) 进行自定义。

## 🐛 常见问题

### Q1: 页面样式显示不正常?

A: 确保浏览器支持CSS Grid和Flexbox,建议使用现代浏览器 (Chrome, Firefox, Edge)。

### Q2: 图表不显示?

A: 检查是否正确加载了Chart.js库。打开浏览器开发者工具查看是否有网络错误。

### Q3: 如何修改默认参数?

A: 在 `index.html` 中修改表单元素的 `value` 属性:

```html
<input type="text" id="stock-code" value="000001">
```

### Q4: 历史记录保存在哪里?

A: 使用浏览器的LocalStorage,数据保存在用户本地。清除浏览器数据会丢失历史记录。

## 🚀 下一步计划

1. **后端集成**: 连接FastAPI后端,实现真实回测
2. **实时更新**: WebSocket推送回测进度
3. **高级图表**: 添加K线图、成交量图等
4. **报告导出**: 支持PDF/Excel导出
5. **策略对比**: 多策略性能对比图表
6. **用户系统**: 登录认证和个人空间

## 📝 开发建议

### 代码规范
- 使用ESLint检查JavaScript代码
- 使用Prettier格式化代码
- 遵循BEM命名规范编写CSS

### 性能优化
- 压缩CSS和JS文件
- 启用Gzip压缩
- 使用CDN加载第三方库
- 懒加载图表数据

### 安全性
- 对用户输入进行验证
- 防止XSS攻击
- 使用HTTPS (生产环境)

## 🤝 贡献指南

欢迎提交Issue和Pull Request!

## 📄 许可证

MIT License

---

**Enjoy Trading! 📈**
