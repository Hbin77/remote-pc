# Stage 1: Build React frontend
FROM node:20-slim AS frontend
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: Python server
FROM python:3.11-slim
WORKDIR /app
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server/ .
COPY agent/ /app/agent_src/
COPY --from=frontend /web/dist /app/static
RUN mkdir -p /app/data
EXPOSE 8900
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8900"]
