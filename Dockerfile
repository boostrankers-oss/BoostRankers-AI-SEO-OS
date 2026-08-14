# Stage 1: Build React Frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Stage 2: Build Python Backend
FROM python:3.11-slim AS backend-build
WORKDIR /app/backend
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .

# Stage 3: Production Image
FROM python:3.11-slim
WORKDIR /app

# Copy backend dependencies and code
COPY --from=backend-build /app /app
COPY --from=frontend-build /app/frontend/dist /app/static

# Install Uvicorn for serving the app
RUN pip install uvicorn[standard]

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]