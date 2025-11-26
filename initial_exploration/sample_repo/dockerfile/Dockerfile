# Sample Dockerfile for tree-sitter exploration
# Multi-stage build with various instructions

# ==================================
# Stage 1: Build stage
# ==================================
FROM node:20-alpine AS builder

# Build arguments
ARG NODE_ENV=production
ARG APP_VERSION=1.0.0

# Labels
LABEL maintainer="developer@example.com"
LABEL version="${APP_VERSION}"
LABEL description="Sample application for tree-sitter exploration"

# Environment variables
ENV NODE_ENV=${NODE_ENV}
ENV APP_HOME=/app
ENV PATH="${APP_HOME}/node_modules/.bin:${PATH}"

# Set working directory
WORKDIR ${APP_HOME}

# Install build dependencies
RUN apk add --no-cache \
    python3 \
    make \
    g++ \
    git

# Copy package files first (for layer caching)
COPY package*.json ./
COPY yarn.lock ./

# Install dependencies
RUN yarn install --frozen-lockfile --production=false

# Copy source code
COPY src/ ./src/
COPY tsconfig.json ./
COPY webpack.config.js ./

# Build application
RUN yarn build && \
    yarn cache clean

# ==================================
# Stage 2: Test stage (optional)
# ==================================
FROM builder AS tester

# Install test dependencies
RUN yarn install --frozen-lockfile

# Copy test files
COPY tests/ ./tests/
COPY jest.config.js ./

# Run tests
RUN yarn test --coverage

# ==================================
# Stage 3: Production stage
# ==================================
FROM node:20-alpine AS production

# Security: run as non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nextjs -u 1001

# Environment
ENV NODE_ENV=production
ENV PORT=3000

# Working directory
WORKDIR /app

# Copy built artifacts from builder
COPY --from=builder --chown=nextjs:nodejs /app/dist ./dist
COPY --from=builder --chown=nextjs:nodejs /app/node_modules ./node_modules
COPY --from=builder --chown=nextjs:nodejs /app/package.json ./

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:${PORT}/health || exit 1

# Expose port
EXPOSE ${PORT}

# Switch to non-root user
USER nextjs

# Volume for persistent data
VOLUME ["/app/data"]

# Entry point and command
ENTRYPOINT ["node"]
CMD ["dist/server.js"]

# ==================================
# Stage 4: Development stage
# ==================================
FROM builder AS development

# Additional dev tools
RUN apk add --no-cache \
    curl \
    vim

# Install all dependencies including devDependencies
RUN yarn install --frozen-lockfile

# Copy all source files
COPY . .

# Development environment variables
ENV NODE_ENV=development
ENV DEBUG=app:*

# Expose debug port
EXPOSE 3000 9229

# Development command with hot reload
CMD ["yarn", "dev"]

# ==================================
# Stage 5: CI stage
# ==================================
FROM builder AS ci

# CI-specific configuration
ENV CI=true
ENV JEST_JUNIT_OUTPUT_DIR=./reports

# Install all dependencies
RUN yarn install --frozen-lockfile

# Copy everything
COPY . .

# Create reports directory
RUN mkdir -p ./reports

# Run linting
RUN yarn lint

# Run type checking
RUN yarn type-check

# Run tests with coverage
RUN yarn test:ci

# Build for deployment
RUN yarn build

# Output: build artifacts are in /app/dist
