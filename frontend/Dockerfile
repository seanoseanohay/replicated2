# ---- build stage ----
# Use Debian-based node to avoid qemu illegal-instruction crashes on arm64
FROM node:20 AS builder

WORKDIR /app

ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL

COPY package.json ./
RUN npm install

COPY . .
RUN npm run build

# ---- runtime stage ----
FROM nginx:1.25-alpine AS runtime

RUN apk add --no-cache gettext

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/templates/default.conf.template

# startup: default the upstream, envsubst the nginx template, then run nginx
CMD ["/bin/sh", "-c", ": \"${BACKEND_URL:=http://backend:8000}\" && envsubst '${PORT} ${BACKEND_URL}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
