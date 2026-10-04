# LeanLens v2 frontend — multi-stage build.
# Build (node) then serve the static bundle with nginx (SPA fallback).

# ---------- build ----------
FROM node:20-alpine AS build

WORKDIR /app

# install dependencies first (layer cache)
COPY package.json package-lock.json ./
RUN npm ci

# build the production bundle
COPY . .
RUN npm run build

# ---------- serve ----------
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx-frontend.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080
