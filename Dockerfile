# syntax=docker/dockerfile:1
# =============================================================================
# Stage 1: Build frontend
# =============================================================================
FROM node:22-alpine AS frontend-builder

WORKDIR /app

# Copy package files and install dependencies
COPY package.json package-lock.json* ./
RUN npm ci --ignore-scripts

# Copy frontend source and build
COPY vite.config.mjs ./
COPY desktop-ui/ ./desktop-ui/
COPY web/ ./web/
RUN npm run frontend:build

# =============================================================================
# Stage 2: Production runtime
# =============================================================================
FROM python:3.13-slim AS runtime

# Install Node.js 22.x for any runtime JS needs
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash appuser

WORKDIR /app

# Copy Python source
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY pyproject.toml README.md ./

# Install Python dependencies
RUN pip install --no-cache-dir --break-system-packages \
    setuptools>=68 \
    && pip install --no-cache-dir --break-system-packages -e .

# Copy built frontend from stage 1
COPY --from=frontend-builder /app/dist ./dist

# Set Python path
ENV PYTHONPATH=/app/src

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 47880

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:47880/health')" || exit 1

# NOTE: openclaw CLI must be installed separately or via a custom entrypoint.
# The install_nas_runtime_stack.py script can be run post-startup to install it:
#   python scripts/install_nas_runtime_stack.py --install-openclaw
#
# For production NAS deploy, consider building a custom image with openclaw
# pre-installed, or mounting the openclaw binary into the container.

ENTRYPOINT ["python", "scripts/run_web_backend.py", "--host", "0.0.0.0", "--port", "47880"]
