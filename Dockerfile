FROM node:22-alpine AS frontend
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY src ./src
COPY public ./public
COPY index.html tsconfig.json vite.config.ts ./
ENV VITE_API_URL=same-origin
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY --from=frontend /build/dist ./dist
ENV STUDYPILOT_DB=/var/data/studypilot.db STATIC_DIR=/app/dist COOKIE_SECURE=true REQUIRE_AI=true
EXPOSE 8000
CMD ["sh", "-c", "python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
