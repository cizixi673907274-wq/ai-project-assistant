FROM node:22-alpine AS builder
RUN corepack enable
WORKDIR /workspace
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml tsconfig.base.json ./
COPY apps/admin-web ./apps/admin-web
COPY packages ./packages
RUN pnpm install --frozen-lockfile
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN pnpm --filter @ai-field/admin-web build

FROM nginx:1.27-alpine
COPY infra/docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /workspace/apps/admin-web/dist /usr/share/nginx/html
EXPOSE 80
