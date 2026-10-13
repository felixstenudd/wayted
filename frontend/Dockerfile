FROM node:24-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

FROM deps AS dev

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

FROM deps AS build

COPY . .
RUN npm run build

FROM deps AS dev-panel-build

# Vite reads it while building.
ARG VITE_MAP_STYLE_URL
ENV VITE_MAP_STYLE_URL=$VITE_MAP_STYLE_URL

COPY . .
RUN npm run build:panel

FROM nginx:1.29-alpine AS dev-panel-prod

COPY nginx.dev-panel.conf /etc/nginx/conf.d/default.conf
COPY --from=dev-panel-build /app/dist-dev-panel /usr/share/nginx/html

EXPOSE 80

FROM nginx:1.29-alpine AS prod

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
