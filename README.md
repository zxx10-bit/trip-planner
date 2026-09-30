# 小星探行 🧭✨

> **小星探行，快乐出行**

基于 HelloAgents 框架构建的智能旅行规划助手。集成高德地图服务，从你**抵达城市的那一刻**开始排布精细时刻表，
自动计算每一段通勤的时长与方式，并按出行人数推荐酒店与高分餐厅 —— 一份完整攻略，直接出发。

## ✨ 功能特点

### 🛰️ 1. 以抵达时刻为起点的精细时刻表

- 输入**抵达时刻**（如 09:30），时刻表自动从这一刻开始向后排布。
- 每一站都标注：**到达时间 · 地点 · 离开时间 · 下一站**。
- 景点间**自动计算通勤时长**，并在时间轴上给出通勤方式、耗时、距离与费用。
- 每日总结当日 `开始时刻`、`结束时刻`、`站点数`、`通勤总时长`；时刻不会排到深夜。

### 👥 2. 出行人数参与推荐

- 首页新增**【出行人数】**输入（1–20 人，含快捷选择）。
- 酒店推荐会说明房晚价格与需要几间房（`(人数+1)/2`）。
- 餐厅推荐按人均消费 × 人数计入预算；交通费用按人数计算（如打车每 4 人一车）。
- 预算明细全部按人数汇总，并给出人均花费。

### 🚇 3. 景点之间自动推荐交通方案

- 勾选可接受的出行偏好：**步行 / 公交 / 地铁 / 打车 / 骑行**。
- 按距离区间与你的偏好匹配最优方式，并调用真实路径规划获取耗时：
  - `< 1.2 km` → 步行优先（备选骑行）
  - `1.2–3.5 km` → 骑行优先（备选步行、公交地铁）
  - `3.5–10 km` → 地铁 / 公交优先（备选打车）
  - `> 10 km` → 地铁 / 公交优先（备选打车、自驾）
- 每个方案都标注**耗时、距离、费用、路线摘要**，并说明**为什么这样选**。

### 🏨 4. 末站酒店 + 周边高分餐厅

- **当日末尾景点附近**推荐酒店：真实评分、价格、距离与房型建议。
- 若行程中有用餐节点，则按**景点周边**搜索高分餐厅（按评分与距离排序），
  并给出**特色菜品 / 招牌菜**、人均消费、距离与电话。

### 📋 5. 全部信息整合为一份完整攻略

无需手动对比信息：概览、预算、地图、每日时刻表、通勤方案、酒店、餐厅、
特色菜品、天气提示全部集中在一个页面，并支持**导出为图片或 PDF**。

### 🤖 6. 右侧悬浮「小星小探员」AI 助手

- 页面右侧常驻悬浮按钮，点击唤起侧边 AI 助手。
- 支持**对话式修改行程**：放慢节奏、改交通方式、换酒店、调整人数、增加美食安排……
- 修改后会**自动重算**时刻表、通勤、餐厅与预算。
- 也能**根据当前攻略回答细节问题**（例如「第 1 天晚饭附近有什么必吃？」）。

### ⚡ 7. 真实的实时进度

- 后端以 **SSE 流式**推送真实阶段进度（景点搜索 → 天气 → 酒店 → 行程编排 →
  通勤计算 → 餐厅酒店 → 攻略整合），**进度随真实工作推进**，不会停在 90% 空等。
- 面板同时显示已用时长与逐条阶段日志；流式通道不可用时自动回退到常规请求。

### 🎨 8. 界面

「小星探行 · 快乐出行」品牌主题、渐光背景、卡片化时刻表、通勤虚线连接、
餐厅招牌菜标签、响应式布局，原有交互逻辑保持不变。

## 🏗️ 技术栈

**后端**：HelloAgents (SimpleAgent) · FastAPI · 高德地图 Web 服务 · MCP (amap-mcp-server) · SSE
**前端**：Vue 3 · TypeScript · Vite · Ant Design Vue · 高德地图 JS API · Axios

## 📁 项目结构

```
trip-planner/
├── backend/
│   ├── app/
│   │   ├── agents/trip_planner_agent.py   # 多智能体协作 + 流式进度
│   │   ├── api/
│   │   │   ├── main.py
│   │   │   └── routes/{trip,poi,map}.py   # 含 /trip/plan/stream 与 /trip/chat
│   │   ├── services/
│   │   │   ├── amap_service.py            # 高德 MCP 封装 + 景点图片
│   │   │   ├── amap_rest.py               # 高德 Web 服务客户端(带缓存)
│   │   │   ├── transport.py               # 交通方式匹配
│   │   │   ├── timeline.py                # 时刻表 / 酒店 / 餐厅编排
│   │   │   ├── dish_catalog.py            # 城市与菜系特色菜品库
│   │   │   ├── llm_service.py
│   │   │   └── unsplash_service.py
│   │   ├── models/schemas.py
│   │   └── config.py
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/AgentSidebar.vue    # 小星小探员 AI 助手
│       ├── components/DayTimeline.vue     # 每日时刻表
│       ├── views/{Home,Result}.vue
│       ├── services/api.ts                # 含 SSE 流式解析
│       └── types/index.ts
└── README.md
```

## 🚀 快速开始

### 前提条件

- Python 3.10+
- Node.js 16+
- 高德地图密钥：Web 服务 API Key（后端）+ Web 端 JS API Key（前端）
- LLM API Key（OpenAI / DeepSeek 等）

### 后端

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate    Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # 填入 AMAP_API_KEY / LLM_* 等
uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端

```bash
cd frontend
npm install
cp .env.example .env          # 填入 VITE_AMAP_WEB_JS_KEY
npm run dev                   # 打开 http://localhost:5173
```

## 📝 使用指南

1. **填写行程基础**：目的地城市、起止日期、**抵达时刻**、**出行人数**、住宿偏好。
2. **选择出行偏好**：勾选可接受的交通方式（步行 / 公交 / 地铁 / 打车 / 骑行）与旅行偏好。
3. 点击 **「生成我的完整攻略」**，实时进度条会展示真实阶段推进。
4. 在结果页查看**每日精细时刻表**、通勤方案、周边高分餐厅与末站酒店。
5. 需要调整？点右侧悬浮按钮召唤 **小星小探员**，用一句话改行程或追问细节。
6. 满意后 **导出为图片 / PDF** 带走。

## 📄 API 文档

启动后端后访问 `http://localhost:8000/docs`。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/trip/plan` | 生成旅行计划（一次性返回） |
| `POST` | `/api/trip/plan/stream` | 生成旅行计划（SSE 实时进度） |
| `POST` | `/api/trip/chat` | 小星小探员：改行程 / 答疑 |
| `GET` | `/api/trip/health` | 旅行规划服务健康检查 |
| `GET` | `/api/poi/photo` | 获取景点图片 |
| `GET` | `/api/map/poi` | 搜索 POI |
| `GET` | `/api/map/weather` | 查询天气 |
| `POST` | `/api/map/route` | 规划路线 |

## 🙏 致谢

- [HelloAgents](https://github.com/datawhalechina/Hello-Agents) · [HelloAgents 框架](https://github.com/jjyaoao/HelloAgents)
- [高德地图开放平台](https://lbs.amap.com/) · [amap-mcp-server](https://github.com/sugarforever/amap-mcp-server)

## 📜 开源协议

CC BY-NC-SA 4.0

---

**小星探行** —— 小星探行，快乐出行 🧭🌈
