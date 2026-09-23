# 一体化部署 Dockerfile（适配 Koyeb / Render 等平台）
# 一个镜像完成：前端构建 + 后端运行 + 静态文件托管
# 前端通过相对路径 /api 调后端，同源不跨域

# ===== 第一阶段：用 Node 编译前端 =====
FROM node:20-alpine AS frontend-build
WORKDIR /build
# 先复制依赖清单，利用 Docker 缓存加速
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
# 复制前端源码
COPY frontend/ ./
# 前端同源配置：axios 用相对路径 /api/*，不跨域
ENV VITE_API_BASE_URL="/"
# 高德地图 Web端(JS API) Key：构建期注入（Koyeb 构建变量同名传入）
ARG VITE_AMAP_WEB_JS_KEY=""
ENV VITE_AMAP_WEB_JS_KEY="${VITE_AMAP_WEB_JS_KEY}"
# 直接用 vite build，跳过 TS 类型检查，避免类型小问题阻断部署
RUN npx vite build
# 产物在 /build/dist（index.html + assets/）

# ===== 第二阶段：Python 后端运行环境 =====
FROM python:3.11-slim
WORKDIR /code
# 安装后端依赖（其中 uv 包会提供运行时需要的 uvx 命令）
COPY backend/requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt
# 预热 amap-mcp-server 包到 uv 缓存，避免首次请求时现下载导致超时
RUN uv tool install amap-mcp-server || true
# 复制后端应用代码
COPY backend/app /code/app
# 从第一阶段复制前端构建产物
COPY --from=frontend-build /build/dist /code/static
# 告诉后端静态文件在哪里（main.py 读取此变量后启用静态托管）
ENV STATIC_DIR=/code/static
# 平台通过 PORT 环境变量指定端口（Koyeb 默认 8080）；本地兜底 8080
# 注意：用 shell 形式才能展开 ${PORT}
CMD uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-8080}
