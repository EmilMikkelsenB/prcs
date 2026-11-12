FROM node:20-slim AS web
WORKDIR /web
COPY web/package.json ./
RUN npm install
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY host/ /app/host/
COPY --from=web /web/dist /app/web/dist
ENV HOST_BIND=0.0.0.0 HOST_PORT=8088 DASH_DATA=/app/data
EXPOSE 8088
CMD ["python3", "-I", "host/app.py"]
