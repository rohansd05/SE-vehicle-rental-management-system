# The Caddy image of docker-compose.prod.yml (D1): builds the React app (the D8
# PWA) with Node, then copies only dist/ into Caddy. deploy/Caddyfile is mounted
# by the compose file.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM caddy:2-alpine
COPY --from=build /app/dist /srv
