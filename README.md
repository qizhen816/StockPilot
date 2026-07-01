# StockPilot

> Explainable AI-powered trading assistant for Chinese A-share portfolios.

StockPilot 是一个面向个人投资者的 A 股盘后决策助手。

它不自动交易，不预测明天涨跌，也不会给出神秘的黑箱分数。它的目标更朴素，也更接近真实交易：

> **每天收盘后，帮你回答一个问题：明天我应该怎样管理自己的持仓？**

StockPilot 会下载你的持仓行情，计算技术指标，评估组合健康度，生成可解释评分，并给出组合视角的行动计划：哪些继续持有，哪些只适合观察，哪些需要降低仓位，哪些可以考虑用更强候选替换。

---

## What It Is

StockPilot 是：

- 盘后复盘助手
- 持仓管理工具
- 可解释决策支持系统
- Markdown / CSV / Dashboard 报告生成器
- Telegram / Email 通知分发器

StockPilot 不是：

- 自动交易机器人
- 高频交易系统
- 收益预测模型
- 全市场量化回测框架
- 保证盈利的荐股工具

所有输出都必须能解释。分数、动作、风险、置信度都必须带原因。

---

## Daily Workflow

一个典型使用方式是：

1. 收盘后更新或确认 `config/portfolio.yaml`
2. 运行日报
3. 查看“明日组合计划”或“今天操作建议”
4. 打开 Dashboard 看组合、评分、候选和图表
5. 根据自己的交易纪律做最终决定

运行命令：

```bash
python daily_report.py
```

输出内容包括：

- 数据下载状态
- 分析口径
- 持仓估值和浮动盈亏
- 组合分析
- 明日组合计划
- 最新指标
- 个股分析
- 个股评分
- 候选扫描
- 决策建议
- 今日总结
- 通知发送状态

报告文件会写入：

```text
reports/daily/YYYY-MM-DD.md
reports/history.csv
```

---

## Market Session Behavior

StockPilot 会区分“估值”和“分析”。

- 持仓估值：始终使用当前可获取的最新行情，尽量反映实时收益
- 技术分析：15:00 前使用上一根完整日线，避免未收盘 K 线污染判断
- 今日总结：15:00 前给出“今天操作建议”，15:00 后给出“明日操作建议”

默认截止时间在 `config/settings.yaml`：

```yaml
market_session:
  analysis_cutoff_time: "15:00"
```

这意味着如果你在 14:30 运行日报，StockPilot 会用昨天收盘后的完整数据做趋势、动量、风险、评分和组合计划；但“持仓估值”仍然按当前可获取行情计算。

---

## Dashboard

Dashboard 是 StockPilot 的交互式工作台，适合盘后认真看一遍组合。

启动：

```bash
streamlit run dashboard.py
```

Dashboard 当前包含：

- **组合**：持仓估值、行业暴露、集中度、组合趋势分、组合风险分
- **计划**：明日组合动作、仓位建议、动作原因、置信度、替换候选
- **评分**：个股分数、风险、相对强弱、个股决策
- **候选**：scanner 选出的候选列表
- **图表**：评分分布和持仓市值
- **明细**：趋势、动量、风险、量能、支撑位和压力位

Dashboard 不会下单。它只是把日报结果变得更容易浏览和比较。

---

## v1.1 Portfolio Decision Engine

v1.1 的重点不是增加更多指标，而是把 StockPilot 的主语从“个股分析”切换到“组合管理”。

过去的问题是：

```text
这只股票 MACD 怎么样？
```

现在的问题是：

```text
明天这个组合应该怎么处理？
```

新增的组合决策引擎会综合：

- 个股评分
- 趋势状态
- 动量状态
- 量能状态
- 风险等级
- 组合内排名
- 相对强弱分
- scanner 候选分数差
- 组合趋势分
- 组合风险分

生成动作：

- `Strong Hold`
- `Hold`
- `Watch`
- `Reduce Position`
- `Replace Candidate`
- `Exit`
- `Avoid Buying`

每个动作都包含：

- 动作
- 风险
- 置信度
- 组合内排名
- 替换候选
- 原因

示例：

```text
兴森科技
动作：强势持有
置信度：88%
原因：
- 组合内排名 1/6
- 分数 90
- 风险较低
- 趋势偏多
- 动量较强
- 量能突破
```

---

## v1.2 Relative Strength Ranking

v1.2 强化了相对强弱，不再只看单只股票自己的指标。

StockPilot 会比较：

- 股票在组合内的涨跌强弱
- 股票在所属行业内的相对位置
- 股票相对组合平均表现的强弱

评分原因会明确写出类似：

```text
相对强弱组合内排名 1/6；行业内排名 1/3
```

这让“强者继续跟踪、弱者谨慎加仓或寻找替换”的逻辑更接近真实组合管理。

v1.2 polish 后，评分最高封顶为 95，置信度最高封顶为 90%。StockPilot 不再输出“完美分”或过度自信的决策概率，置信度只表示系统对当前决策依据的一致性。

---

## v1.3 Position Management Engine

v1.3 增加了独立的仓位管理引擎。它回答的不是“这只股票强不强”，而是：

```text
这只已经持有的股票，明天应该保留多少仓位？
```

仓位建议会综合：

- 当前持股数量
- 成本价和现价
- 浮动盈亏
- 趋势、动量、风险
- 距离压力位的空间
- ATR 止损和跟踪止损
- 组合集中度和行业暴露

输出示例：

```text
兴森科技
当前：100 股
建议：75 股
动作：部分止盈
原因：
- 价格接近压力位
- 趋势仍健康，但需要保护已有利润
- 现金管理实现前不建议额外加仓
```

仓位状态包括：

- `FULL`：保留当前仓位
- `ACCUMULATE`：保留核心仓，适合部分止盈
- `NORMAL`：标准仓
- `LIGHTEN`：轻仓防守
- `EXIT`：退出持仓

当前版本不会主动建议额外买入，因为系统还没有现金管理、最大仓位和风险预算模块。强势品种会优先给出“继续持有”或“保留核心仓”，避免在没有资金约束的情况下给出过度进攻建议。

v1.3.1 对决策质量做了进一步打磨：

- 仓位管理新增趋势阶段：上升初期、上升中段、上升后段、趋势内回调、趋势破位
- 趋势内回调不会被直接当成破位处理，只有 BREAKDOWN 才会重减仓
- 相对强弱改为 5 日、20 日、60 日加权，减少单日涨跌噪音
- 个股评分加入长期趋势惩罚，避免 MA60 下方的反弹被过度高估
- 替换建议加入替换置信度和换仓成本，分数高不再自动等于应该替换
- 决策动作加入执行优先级：立即、今日、本周、观察、未来
- 风险拆分为波动风险、趋势风险、集中度风险和组合风险

---

## Configuration

主要配置文件：

```text
config/settings.yaml
config/portfolio.yaml
```

### Portfolio

示例：

```yaml
stocks:
  "002436":
    name: 兴森科技
    cost: 50.411
    shares: 100
    sector: PCB

  "002156":
    name: 通富微电
    cost: 74.041
    shares: 100
    sector: Semiconductor
```

### Decision Thresholds

组合决策阈值在 `config/settings.yaml`：

```yaml
portfolio_decision:
  strong_hold_score_threshold: 85
  hold_score_threshold: 70
  reduce_score_threshold: 55
  exit_score_threshold: 40
  replace_score_threshold: 60
  replacement_min_score_gap: 12
  minimum_confidence: 0.55
  maximum_confidence: 0.90
```

这些值决定什么时候强势持有、持有、观察、减仓、退出或寻找替换候选。

### Position Management

仓位管理阈值在 `config/settings.yaml`：

```yaml
position_manager:
  full_position_pct: 1.0
  accumulate_position_pct: 0.75
  normal_position_pct: 0.50
  lighten_position_pct: 0.25
  exit_position_pct: 0.0
  near_resistance_pct: 0.03
  wide_resistance_pct: 0.08
  profit_protection_levels: [0.05, 0.10, 0.15, 0.20]
  atr_stop_multiplier: 2.0
  pullback_position_pct: 1.0
  late_uptrend_position_pct: 0.75
  breakdown_position_pct: 0.25
```

这些值决定“接近压力位”“盈利保护”“ATR 止损”等仓位管理规则。

### Market Session

```yaml
market_session:
  analysis_cutoff_time: "15:00"
```

15:00 前运行时，分析使用上一完整收盘日；15:00 后运行时，分析使用最新日线。

### Notifications

通知默认关闭，避免误发。

开启 Telegram 或 Email 前，需要在 `config/settings.yaml` 打开对应开关，并设置环境变量：

```bash
export STOCKPILOT_TELEGRAM_BOT_TOKEN="..."
export STOCKPILOT_TELEGRAM_CHAT_ID="..."

export STOCKPILOT_EMAIL_USERNAME="..."
export STOCKPILOT_EMAIL_PASSWORD="..."
export STOCKPILOT_EMAIL_SENDER="..."
```

---

## Project Structure

```text
stock-pilot/
├── config/
│   ├── portfolio.yaml
│   └── settings.yaml
├── docs/
│   ├── ARCHITECTURE.md
│   ├── RULES.md
│   ├── ROADMAP.md
│   └── TASKS.md
├── stock_pilot/
│   ├── ai_summary.py
│   ├── analyzer.py
│   ├── fetcher.py
│   ├── indicators.py
│   ├── market_session.py
│   ├── notification.py
│   ├── pipeline.py
│   ├── portfolio.py
│   ├── portfolio_decision.py
│   ├── position_manager.py
│   ├── reporter.py
│   ├── scanner.py
│   ├── scorer.py
│   ├── strategy.py
│   ├── models.py
│   ├── settings.py
│   └── logging_config.py
├── dashboard.py
├── daily_report.py
├── reports/
├── tests/
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## Architecture

StockPilot follows a strict one-way pipeline:

```text
Fetcher
↓
Indicators
↓
Analyzer
↓
Strategy
↓
Scorer
↓
Portfolio Decision
↓
Reporter
↓
Notification
```

Rules:

- Fetcher only downloads data
- Indicators only calculate indicators
- Analyzer only interprets indicators
- Scorer only produces explainable scores
- Portfolio Decision only manages portfolio actions
- Reporter only renders output
- Notification only sends generated reports

No module may skip layers or depend on higher layers.

---

## Tech Stack

Python 3.12+

Core libraries:

- akshare
- pandas
- numpy
- PyYAML
- rich
- matplotlib
- streamlit

StockPilot intentionally avoids TA-Lib. Indicators are implemented with pandas and numpy for portability and maintainability.

---

## Development Roadmap

Completed:

- v0.1 Foundation
- v0.2 Indicator Engine
- v0.3 Portfolio Engine
- v0.4 Analyzer
- v0.5 Scoring Engine
- v0.6 Report Engine
- v0.7 AI Summary
- v0.8 Market Scanner
- v0.9 Dashboard
- v1.0 Notifications
- v1.1 Portfolio Decision Engine
- v1.2 Relative Strength Ranking

Future directions:

- Relative strength vs CSI300 / sector / portfolio
- Replacement recommendation quality
- Sector rotation
- Intraday quality score
- Tomorrow trading plan
- Market overview
- Fund-manager style AI daily review

The long-term goal is:

```text
Technical Indicator Viewer
↓
Portfolio Decision Assistant
↓
AI Trading Coach
```

---

## Quality Standard

StockPilot is designed as a production-quality open source project.

Code should be:

- readable
- testable
- deterministic
- modular
- explainable

Every public function should include type hints and a docstring. Business logic should be covered by focused unit tests. Configuration values should live in YAML or dataclasses, not hidden constants.

---

## Disclaimer

StockPilot is a decision-support tool. It does not provide guaranteed investment advice, does not execute trades, and does not replace your own risk management.

The final decision is always yours.
