#!/bin/bash
set -e

# Run as root to set up directories
echo "Fixing permissions and creating symlinks..."

# Create /app directory structure first
mkdir -p /app/memory/workflows /app/rag/faiss /app/logs 2>/dev/null || true

# Create /root/claude-brain directory structure and symlink to /app
mkdir -p /root/claude-brain
rm -f /root/claude-brain/memory /root/claude-brain/rag /root/claude-brain/logs 2>/dev/null || true
ln -s /app/memory /root/claude-brain/memory
ln -s /app/rag /root/claude-brain/rag
ln -s /app/logs /root/claude-brain/logs

# Ensure permissions
chmod -R 777 /app/memory /app/rag /app/logs 2>/dev/null || true

# Run uvicorn
echo "Starting uvicorn..."
exec uvicorn api.main:app --host 0.0.0.0 --port 8765
