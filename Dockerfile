# Multi-stage Dockerfile for Claude Brain
# Optimized for small image size and security

# Stage 1: Builder
FROM python:3.12-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 brainuser

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/brainuser/.local

# Copy application code
COPY . .

# Set ownership to non-root user
RUN chown -R brainuser:brainuser /app

# Switch to non-root user
USER brainuser

# Add local pip to PATH
ENV PATH=/home/brainuser/.local/bin:$PATH

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8765/ || exit 1

# Expose port
EXPOSE 8765

# Default command: Run API server
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8765"]
