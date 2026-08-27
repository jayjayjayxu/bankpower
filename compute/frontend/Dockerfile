FROM node:22-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_APP_BASE=/
ARG VITE_API_BASE_URL=/api
ARG VITE_POWER_SITE_URL
ENV VITE_APP_BASE=$VITE_APP_BASE
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_POWER_SITE_URL=$VITE_POWER_SITE_URL
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
