# syntax=docker/dockerfile:1
FROM node:24-alpine AS frontend-build

WORKDIR /app/frontend

ARG VITE_SENTRY_DSN=
ARG VITE_SENTRY_SEND_DEFAULT_PII=

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM caddy:2-alpine

COPY config/Caddyfile /etc/caddy/Caddyfile
COPY --from=frontend-build /app/frontend/dist /srv/frontend
