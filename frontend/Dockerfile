# =====================================================================
# Karabuk FWI — frontend image (Next.js 16, multi-stage)
# =====================================================================
# Starter template. Smoke-test before relying on it; see
# docs/DEPLOYMENT_PLAN.md for the rollout checklist.
# =====================================================================

# ---- 1. Install deps ----
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# ---- 2. Build ----
FROM node:20-alpine AS builder
WORKDIR /app

# NEXT_PUBLIC_* values are baked in at build time, so the API URL must
# be passed when we `docker build` (compose handles this via `args:`).
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# ---- 3. Runtime ----
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Copy only what `next start` needs.
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public

EXPOSE 3000
CMD ["npm", "run", "start"]
