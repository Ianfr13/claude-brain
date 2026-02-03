# Claude Brain - Setup Guide

Complete setup instructions for Claude Brain infrastructure with Docker Compose, Neo4j, Redis, and API server.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Detailed Setup](#detailed-setup)
- [Services Overview](#services-overview)
- [Configuration](#configuration)
- [Verification & Testing](#verification--testing)
- [Troubleshooting](#troubleshooting)
- [Common Tasks](#common-tasks)

---

## Prerequisites

### System Requirements

- **OS**: Linux, macOS, or Windows (WSL2)
- **Docker**: 20.10+
- **Docker Compose**: 1.29+
- **Python**: 3.9+
- **RAM**: Minimum 8GB (16GB recommended for Neo4j + Redis + API)
- **Disk**: 10GB+ free space

### Install Prerequisites

#### macOS (using Homebrew)

```bash
# Install Docker Desktop
brew install --cask docker

# Install Docker Compose (included with Docker Desktop)
# Verify installation
docker --version
docker-compose --version
```

#### Ubuntu/Debian

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Add your user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify installation
docker --version
docker-compose --version
```

#### Windows (WSL2)

```bash
# From WSL2 terminal, follow Ubuntu/Debian instructions
# Then install Docker Desktop for Windows with WSL2 support
```

---

## Quick Start

The fastest way to get everything running:

```bash
# Navigate to project directory
cd /root/claude-brain

# Run the setup script
./scripts/setup_brain.sh

# Wait for all services to be healthy
docker-compose ps

# View logs
docker-compose logs -f
```

Expected output after setup:
```
NAME                    STATUS
claude-brain-neo4j      Up (healthy)
claude-brain-redis      Up (healthy)
claude-brain-api        Up (healthy)
```

---

## Detailed Setup

### Step 1: Clone & Navigate

```bash
git clone <your-repo-url> /root/claude-brain
cd /root/claude-brain
```

### Step 2: Prepare Environment

```bash
# Copy .env template to .env
cp .env.example .env

# Edit .env with your configuration
nano .env
```

**Critical variables to set:**

```env
# API Keys (get these from providers)
ANTHROPIC_API_KEY=sk-ant-...
OPENROUTER_API_KEY=sk-or-v1-...

# Neo4j & Redis passwords (change these!)
NEO4J_PASSWORD=yourSecurePassword
REDIS_PASSWORD=yourSecureRedisPassword
```

### Step 3: Create Directories

```bash
# The setup script does this automatically, but you can do it manually:
mkdir -p memory rag/faiss rag/chunks logs config data/neo4j
chmod 755 logs
```

### Step 4: Configure Neo4j Plugins (Optional)

Create `config/neo4j-plugins.txt`:

```txt
# Neo4j plugins (auto-downloaded)
apoc
gds
```

### Step 5: Start Services

```bash
# Option A: Using setup script (RECOMMENDED)
./scripts/setup_brain.sh

# Option B: Manual Docker Compose
docker-compose up -d

# Option C: Quick setup (skip health checks)
./scripts/setup_brain.sh --fast

# Option D: Verbose debugging
./scripts/setup_brain.sh --verbose
```

### Step 6: Verify Services

```bash
# Check all services are running
docker-compose ps

# Check logs for errors
docker-compose logs neo4j
docker-compose logs redis
docker-compose logs brain-api

# Test Neo4j connection
docker-compose exec neo4j cypher-shell -u neo4j -p brainpassword "RETURN 1"

# Test Redis connection
docker-compose exec redis redis-cli -a brainredis ping

# Test API (when built)
curl http://localhost:8765/
```

---

## Services Overview

### 1. Neo4j (Graph Database)

**Purpose**: Knowledge graph storage, relationships, and query optimization

- **Port**: 7474 (Browser UI), 7687 (Bolt protocol)
- **Image**: `neo4j:5.15-community`
- **Memory**: 2GB heap, 1GB pagecache
- **Plugins**: APOC, GDS (Graph Data Science)
- **Username**: `neo4j`
- **Password**: `brainpassword` (change in .env)

**Access**:

```bash
# Browser UI
open http://localhost:7474

# CLI access
docker-compose exec neo4j cypher-shell -u neo4j -p brainpassword

# Run Cypher query
docker-compose exec neo4j cypher-shell -u neo4j -p brainpassword \
  "MATCH (n) RETURN count(n) as node_count"
```

### 2. Redis (Cache Layer)

**Purpose**: Fast caching for queries, sessions, and temporary data

- **Port**: 6379
- **Image**: `redis:7-alpine`
- **Memory**: 512MB limit
- **Password**: `brainredis` (change in .env)
- **Persistence**: AOF (Append-Only File)

**Access**:

```bash
# CLI access
docker-compose exec redis redis-cli -a brainredis

# Check memory
docker-compose exec redis redis-cli -a brainredis info memory

# Monitor commands in real-time
docker-compose exec redis redis-cli -a brainredis monitor

# Clear cache
docker-compose exec redis redis-cli -a brainredis FLUSHALL
```

### 3. Claude Brain API

**Purpose**: Main application server for brain operations

- **Port**: 8765
- **Language**: Python (FastAPI)
- **Depends on**: Neo4j + Redis healthy
- **Memory**: 4GB limit
- **Healthcheck**: HTTP endpoint `/` every 30s

**Access**:

```bash
# API root
curl http://localhost:8765/

# View logs
docker-compose logs -f brain-api

# Rebuild (if you modify code)
docker-compose build --no-cache brain-api
```

---

## Configuration

### Environment Variables

Key configuration options in `.env`:

```env
# Paths
BRAIN_DIR=/root/claude-brain
DB_PATH=/root/claude-brain/memory/brain.db
RAG_DIR=/root/claude-brain/rag

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=brainpassword

# Redis
REDIS_URL=redis://:brainredis@localhost:6379/0
CACHE_TTL_SECONDS=86400

# API
API_HOST=0.0.0.0
API_PORT=8765
LOG_LEVEL=INFO

# Features
ENABLE_NEO4J=true
ENABLE_REDIS=true
ENABLE_AUTO_REBUILD=true
```

### Docker Compose Override

To customize services, create `docker-compose.override.yml`:

```yaml
version: '3.8'
services:
  neo4j:
    environment:
      NEO4J_server_memory_heap_max__size: 4G  # Increase heap
  redis:
    command: redis-server --appendonly yes --requirepass NEWPASSWORD
```

---

## Verification & Testing

### Health Checks

All services include automatic health checks:

```bash
# View health status
docker-compose ps

# Manual health test
docker inspect claude-brain-neo4j | grep -A 20 '"Health"'
```

### Connectivity Tests

```bash
# Neo4j
docker-compose exec -T neo4j cypher-shell -u neo4j -p brainpassword "RETURN 1"

# Redis
docker-compose exec -T redis redis-cli -a brainredis ping

# API
curl -v http://localhost:8765/
```

### Database Initialization

```bash
# Create Neo4j schema
docker-compose exec neo4j cypher-shell -u neo4j -p brainpassword <<'EOF'
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Memory) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Learning) REQUIRE n.id IS UNIQUE;
CREATE INDEX IF NOT EXISTS FOR (n:Memory) ON (n.created_at);
EOF

# Verify schema
docker-compose exec neo4j cypher-shell -u neo4j -p brainpassword \
  "SHOW CONSTRAINTS"
```

### Performance Testing

```bash
# Check Neo4j performance
docker-compose exec neo4j cypher-shell -u neo4j -p brainpassword \
  "PROFILE MATCH (n) RETURN count(n)"

# Check Redis performance
docker-compose exec redis redis-cli -a brainredis --latency-history

# Check container resource usage
docker stats --no-stream
```

---

## Troubleshooting

### Services Won't Start

**Symptom**: `docker-compose up` fails or services crash immediately

**Solution**:

```bash
# Check detailed logs
docker-compose logs --tail 50 neo4j

# Check Docker daemon
docker info

# Verify Docker resources
docker system df

# Rebuild everything
docker-compose down -v
docker system prune -a
docker-compose up -d --build
```

### Neo4j Won't Connect

**Symptom**: `Connection refused` when accessing Neo4j

**Solution**:

```bash
# Check if Neo4j is running
docker-compose ps neo4j

# Check logs
docker-compose logs neo4j

# Verify password
docker-compose exec neo4j cypher-shell -u neo4j -p brainpassword "RETURN 1"

# Reset password (if needed)
docker-compose exec neo4j cypher-shell -u neo4j -p neo4j "ALTER USER neo4j SET PASSWORD 'brainpassword'"
```

### Out of Memory Errors

**Symptom**: Services killed with exit code 137

**Solution**:

```bash
# Check Docker memory limit
docker info | grep "Memory:"

# Increase Docker memory in Docker Desktop settings

# Or reduce Neo4j heap in docker-compose.yml:
NEO4J_server_memory_heap_max__size=1G  # from 2G
```

### Redis Connection Issues

**Symptom**: `NOAUTH Authentication required` or timeout

**Solution**:

```bash
# Verify Redis password
docker-compose exec redis redis-cli -a brainredis ping

# Check Redis config
docker-compose exec redis redis-cli -a brainredis CONFIG GET requirepass

# Restart Redis
docker-compose restart redis
```

### API Won't Build

**Symptom**: `docker-compose build` fails

**Solution**:

```bash
# Check Dockerfile
cat Dockerfile

# Build with verbose output
docker-compose build --no-cache --progress=plain brain-api

# Check Python dependencies
cat requirements.txt | head -20

# Install deps locally
pip install -r requirements.txt
```

### Port Already in Use

**Symptom**: `Address already in use` error

**Solution**:

```bash
# Find process using port 7474 (Neo4j)
lsof -i :7474
kill -9 <PID>

# Or change port in docker-compose.yml
# ports:
#   - "127.0.0.1:7475:7474"  # Changed from 7474

# Restart services
docker-compose down
docker-compose up -d
```

### Slow Performance

**Symptom**: Queries take too long, API responses slow

**Solution**:

```bash
# Check Neo4j cache hit rate
docker-compose exec neo4j cypher-shell -u neo4j -p brainpassword \
  "SHOW TRANSACTIONS"

# Increase memory allocation
# In docker-compose.yml, increase limits:
# limits:
#   memory: 8G
# reservations:
#   memory: 4G

# Check Redis hit rate
docker-compose exec redis redis-cli -a brainredis INFO stats

# Monitor resource usage
docker stats
```

---

## Common Tasks

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f neo4j
docker-compose logs -f redis
docker-compose logs -f brain-api

# Last 100 lines, specific service
docker-compose logs --tail 100 neo4j

# Follow output from a specific container
docker logs -f claude-brain-api
```

### Stop/Restart Services

```bash
# Stop all services (keeps data)
docker-compose stop

# Stop and remove containers
docker-compose down

# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart neo4j

# Full reset (removes volumes!)
docker-compose down -v
```

### Backup Data

```bash
# Backup Neo4j
docker-compose exec neo4j neo4j-admin database dump neo4j > backup-neo4j.dump

# Backup Redis
docker-compose exec redis redis-cli -a brainredis --rdb /data/dump.rdb
docker cp claude-brain-redis:/data/dump.rdb ./backup-redis.rdb

# Backup SQLite
cp memory/brain.db memory/brain.db.backup
```

### Database Management

```bash
# Delete all Neo4j data (CAREFUL!)
docker-compose exec neo4j cypher-shell -u neo4j -p brainpassword \
  "MATCH (n) DETACH DELETE n"

# Clear Redis cache
docker-compose exec redis redis-cli -a brainredis FLUSHALL

# List all nodes in Neo4j
docker-compose exec neo4j cypher-shell -u neo4j -p brainpassword \
  "MATCH (n) RETURN labels(n), count(*) as count"
```

### Scale Services

```bash
# Increase Neo4j heap memory (edit docker-compose.yml)
NEO4J_server_memory_heap_max__size: 4G

# Increase Redis memory limit
memory: 1G

# Rebuild with new config
docker-compose down -v
docker-compose up -d
```

---

## Advanced Setup

### Using .env Secrets

For production, use a secrets file:

```bash
# Create secrets file with restrictive permissions
echo "SUPER_SECRET_KEY" > .secrets
chmod 600 .secrets

# Reference in docker-compose.yml
environment:
  - SECRET_KEY_FILE=/run/secrets/brain_secret
secrets:
  brain_secret:
    file: .secrets
```

### Custom Docker Networks

To connect other services to Claude Brain:

```yaml
# In other docker-compose.yml files
networks:
  claude-brain-network:
    external: true
```

```bash
# Services will share the same network
docker-compose exec brain-api curl http://redis:6379
```

### Production Deployment

For production, use `docker-compose.prod.yml`:

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

Key differences:
- More restrictive resource limits
- Production-grade logging
- Network isolation
- SSL/TLS support

---

## Getting Help

### Useful Commands

```bash
# Check overall health
docker-compose ps
docker stats
docker system df

# Get detailed service info
docker inspect claude-brain-neo4j | jq '.[] | .State'

# Check network connectivity between containers
docker network inspect claude-brain-network

# Clean up unused resources
docker system prune

# View docker events in real-time
docker events --filter 'container=claude-brain'
```

### Documentation Links

- **Docker Compose**: https://docs.docker.com/compose/
- **Neo4j**: https://neo4j.com/docs/
- **Redis**: https://redis.io/documentation
- **Claude Brain**: See `/root/claude-brain/README.md`

### Support

If you encounter issues:

1. Check logs: `docker-compose logs -f`
2. Verify prerequisites: `./scripts/setup_brain.sh --verbose`
3. Review troubleshooting section above
4. Check Docker daemon health: `docker info`

---

## Next Steps

After successful setup:

1. **Load API Keys**: Update `.env` with your API credentials
2. **Initialize Graph**: Run `brain graph sync` to populate Neo4j
3. **Test Connectivity**: Visit Neo4j browser at http://localhost:7474
4. **Build API**: Run `docker-compose build brain-api` if needed
5. **Start Using**: Use the brain CLI or API to manage knowledge

Happy using Claude Brain!
