#
# Multi-stage build:
# - builder: installs deps + builds CRA bundle
# - runtime: serves static build via nginx
#
FROM node:20-bullseye-slim AS builder

WORKDIR /app

COPY package.json yarn.lock* /app/
RUN yarn install --frozen-lockfile

COPY . /app

ARG REACT_APP_BACKEND_URL=https://omnimine.demoapi.agrayianailabs.com/
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL

RUN yarn build


FROM nginx:1.27-alpine AS runtime

COPY --from=builder /app/build /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
