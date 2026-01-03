# QSCI Trading Bot - Production Dockerfile
# Optimized for Koyeb deployment with TA-Lib support

# Stage 1: Build TA-Lib
FROM python:3.12-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Download and build TA-Lib
WORKDIR /tmp
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    cd .. && \
    rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# Stage 2: Production image
FROM python:3.12-slim

# Copy TA-Lib from builder
COPY --from=builder /usr/lib/libta_lib* /usr/lib/
COPY --from=builder /usr/include/ta-lib /usr/include/ta-lib

# Install runtime dependencies + build tools for pip packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    build-essential \
    gcc \
    g++ \
    gfortran \
    && rm -rf /var/lib/apt/lists/* \
    && ldconfig

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies, then remove build tools to keep image small
RUN pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential gcc g++ gfortran \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/data /app/logs /app/temp /app/config

# Create non-root user for security
RUN useradd -m -u 1000 qsci && chown -R qsci:qsci /app
USER qsci

# Environment variables (overridden by Koyeb)
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV TZ=UTC
# Koyeb uses PORT env variable
ENV PORT=8080
ENV HEALTH_CHECK_PORT=8080

# Expose port for health check HTTP server
EXPOSE 8080

# Health check (uses the HTTP endpoint from health_dashboard.py)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health/live || exit 1

# Run the live trader with health dashboard
CMD ["python", "qsci_live_trader.py"]

