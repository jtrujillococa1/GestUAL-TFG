FROM node:22-alpine AS dependencies

WORKDIR /app

COPY package*.json ./

RUN npm ci

FROM dependencies AS development

COPY . .

EXPOSE 9002

CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0"]

FROM dependencies AS builder

WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1

COPY . .

ARG NEXT_PUBLIC_BASE_PATH=""
ARG NEXT_PUBLIC_API_URL="http://localhost:8000"

ENV NEXT_PUBLIC_BASE_PATH=${NEXT_PUBLIC_BASE_PATH}
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

RUN npm run build

FROM node:22-alpine AS runtime

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 9002

CMD ["node", "server.js"]