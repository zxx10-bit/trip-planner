# Hugging Face Spaces 一体化部署 Dockerfile
# 作用：在一个镜像里完成「前端构建 + 后端运行 + 静态托管」
# 部署到 HF Space 仓库时此文件会被重命名为 Dockerfile（放在仓库根目录）

# ===== 第一阶段：用 Node 编译前端 =====
FROM node:20-alpine AS frontend-build
WORKDIR /build
# 先复制依赖清单，利用 Docker 缓存加速
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
# 复制前端源码
COPY frontend/ ./
# 关键：设 VITE_API_BASE_URL="/"
# 这样 axios 用相对路径调 /api/*，同源不跨域，CORS 完全省掉
ENV VITE_API_BASE_URL="/"
RUN npm run build
# 产物在 /build/dist（index.html + assets/）

# ===== 第二阶段：Python 后端运行环境 =====
FROM python:3.11-slim
WORKDIR /code
# 安装后端依赖
COPY backend/requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt
# 复制后端应用代码
COPY backend/app /code/app
# 从第一阶段复制前端构建产物到 /code/static
COPY --from=frontend-build /build/dist /code/static
# 告诉后端静态文件在哪里（main.py 会读取这个变量）
ENV STATIC_DIR=/code/static
# HF Space 要求服务监听 7860 端口
EXPOSE 7860
# 启动 uvicorn（线上不使用热重载）
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "7860"]
