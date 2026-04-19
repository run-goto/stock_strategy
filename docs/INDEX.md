# 文档组织结构

```
docs/
│
├── README.md                    # 📚 文档中心 (导航索引) ⭐ 从这里开始
│   ├── 快速导航
│   ├── 文档分类
│   ├── 学习路径
│   └── 常见问题查找
│
├── Architecture.md              # 🏛️ 架构设计文档
│   ├── 四层架构概览
│   ├── 各层详细说明
│   ├── 层间交互流程
│   └── 代码映射关系
│
├── SoftwareManual.md            # 📖 软件说明文档 (最全面)
│   ├── 项目概述
│   ├── 系统架构 (四层详解)
│   ├── 技术栈
│   ├── 项目结构
│   ├── 快速开始
│   ├── 核心功能 (按四层组织)
│   ├── 策略列表
│   ├── 自定义开发
│   ├── 测试说明
│   └── 常见问题
│
├── APIReference.md              # 🔌 API接口文档
│   ├── API概述
│   ├── 健康检查接口
│   ├── 策略管理接口
│   ├── 扫描任务接口
│   ├── 回测接口
│   ├── 数据管理接口
│   ├── 调用示例 (Python/JS/cURL)
│   └── 错误码说明
│
├── ShortTermStrategies.md       # 📈 短线策略详解
│   ├── ST-01: 双均线趋势策略
│   ├── ST-02: 低位123结构突破
│   ├── ST-03: MACD底背离双突破
│   ├── ST-04: 向上突破缺口追涨
│   ├── ST-05: 缺口回踩支撑买入
│   └── ST-06: 强势涨停突破
│
├── BacktraderGuide.md           # 🔧 Backtrader使用指南
│   ├── 快速开始
│   ├── 核心组件说明
│   ├── 回测引擎用法
│   ├── 参数优化
│   ├── 高级功能
│   └── 最佳实践
│
├── Strategies.md                # 📋 原始策略需求规格
│   ├── 6个量化策略详细规格
│   ├── 3个选股过滤器说明
│   ├── 输出规范
│   └── 开发优先级
│
└── PRD.md                       # 📝 产品需求文档
    ├── 产品目标
    ├── 用户角色
    ├── 功能需求
    ├── 非功能需求
    └── 验收标准

其他文档:
└── frontend/README.md           # 🖥️ 前端使用说明
```

---

## 📊 文档用途速查

| 文档 | 主要用途 | 阅读时间 | 适合人群 |
|------|---------|---------|---------|
| **README.md** | 文档导航索引 | 5分钟 | 所有人 |
| **SoftwareManual.md** | 完整使用手册 | 30分钟 | 所有用户 |
| **Architecture.md** | 理解系统设计 | 15分钟 | 技术人员 |
| **APIReference.md** | API集成参考 | 20分钟 | 开发者 |
| **ShortTermStrategies.md** | 策略逻辑说明 | 25分钟 | 量化研究员 |
| **BacktraderGuide.md** | 回测框架教程 | 30分钟 | 策略开发者 |
| **Strategies.md** | 原始需求规格 | 20分钟 | 产品/研发 |
| **PRD.md** | 产品定位说明 | 15分钟 | 产品/管理 |

---

## 🎯 推荐阅读顺序

### 新用户
```
README.md → SoftwareManual.md → Architecture.md → frontend/README.md
```

### 策略开发者
```
README.md → ShortTermStrategies.md → BacktraderGuide.md → SoftwareManual.md
```

### API集成者
```
README.md → APIReference.md → Architecture.md → SoftwareManual.md
```

### 产品经理
```
README.md → PRD.md → Strategies.md → SoftwareManual.md
```

---

## 💡 文档使用技巧

1. **使用Ctrl+F搜索**: 在文档中快速查找关键词
2. **查看目录**: 每个文档都有清晰的章节划分
3. **代码示例**: 大多数文档都包含可直接运行的代码
4. **交叉引用**: 文档之间相互链接，方便跳转
5. **Swagger UI**: 访问 http://127.0.0.1:8000/docs 在线测试API

---

**提示**: 建议将 `docs/README.md` 加入书签，作为文档入口！🔖

