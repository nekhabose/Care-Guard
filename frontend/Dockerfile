# CareGuard dashboard — build the Vite SPA, serve it with nginx.
FROM node:20-alpine AS build

WORKDIR /app

# Install deps from the lockfile for reproducible builds.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# API base is empty: nginx serves the SPA and proxies /auth, /dashboard, etc.
# to the backend on the same origin (no CORS, nothing host-specific baked in).
ENV VITE_API_BASE_URL=""
RUN npm run build

FROM nginx:1.27-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
