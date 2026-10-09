FROM node:20-alpine AS build
WORKDIR /app
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile --network-timeout 600000
COPY . .
# Same-origin API (nginx proxies /api), no source maps, no hosted preview scripts.
ENV REACT_APP_BACKEND_URL="" GENERATE_SOURCEMAP=false ENABLE_HEALTH_CHECK=false NODE_ENV=production
RUN sed -i '/emergent-main.js/d' public/index.html && yarn build

FROM nginx:1.27-alpine
RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/build /usr/share/nginx/html
