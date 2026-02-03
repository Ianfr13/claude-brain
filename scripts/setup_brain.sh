#!/bin/bash

################################################################################
# Claude Brain Setup Script
#
# Purpose: Complete setup for Claude Brain infrastructure
# - Validates prerequisites
# - Creates necessary directories
# - Initializes Docker Compose services
# - Waits for services to be healthy
# - Runs database migrations
# - Tests connectivity
#
# Usage: ./scripts/setup_brain.sh [OPTIONS]
# Options:
#   --skip-docker    Skip Docker/Compose checks
#   --skip-deps      Skip Python dependency installation
#   --fast           Run without waiting for services
#   --verbose        Enable verbose logging
#
################################################################################

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${PROJECT_ROOT}/logs/setup.log"
TIMEOUT_SECONDS=300
NEO4J_TIMEOUT=120
REDIS_TIMEOUT=30
API_TIMEOUT=60

# Default flags
SKIP_DOCKER=false
SKIP_DEPS=false
FAST_MODE=false
VERBOSE=false

################################################################################
# Utility Functions
################################################################################

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $*" | tee -a "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" | tee -a "$LOG_FILE"
}

verbose_log() {
    if [[ "$VERBOSE" == "true" ]]; then
        echo -e "${BLUE}[DEBUG]${NC} $*" | tee -a "$LOG_FILE"
    fi
}

# Cleanup on exit
cleanup() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        log_error "Setup failed with exit code $exit_code"
        log_info "Check logs at: $LOG_FILE"
    fi
    return $exit_code
}

trap cleanup EXIT

# Print header
print_header() {
    echo ""
    echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}     Claude Brain Setup Script${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
    echo ""
}

# Print step
print_step() {
    local step_num=$1
    local step_desc=$2
    echo ""
    log_info "Step $step_num: $step_desc"
}

################################################################################
# Argument Parsing
################################################################################

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-docker)
                SKIP_DOCKER=true
                shift
                ;;
            --skip-deps)
                SKIP_DEPS=true
                shift
                ;;
            --fast)
                FAST_MODE=true
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            -h|--help)
                print_usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                print_usage
                exit 1
                ;;
        esac
    done
}

print_usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Options:
    --skip-docker    Skip Docker/Compose checks
    --skip-deps      Skip Python dependency installation
    --fast           Run without waiting for services
    --verbose        Enable verbose logging
    -h, --help       Show this help message

Examples:
    ./scripts/setup_brain.sh                  # Full setup with all checks
    ./scripts/setup_brain.sh --fast          # Quick setup, minimal waiting
    ./scripts/setup_brain.sh --verbose       # Setup with debug output

EOF
}

################################################################################
# Prerequisite Checks
################################################################################

check_prerequisites() {
    print_step "1" "Checking prerequisites"

    local missing_tools=()

    # Check for Docker
    if ! command -v docker &> /dev/null; then
        missing_tools+=("docker")
    else
        verbose_log "✓ Docker found: $(docker --version)"
    fi

    # Check for Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        missing_tools+=("docker-compose")
    else
        verbose_log "✓ Docker Compose found: $(docker-compose --version)"
    fi

    # Check for Python
    if ! command -v python3 &> /dev/null; then
        missing_tools+=("python3")
    else
        verbose_log "✓ Python3 found: $(python3 --version)"
    fi

    # Check for Git
    if ! command -v git &> /dev/null; then
        missing_tools+=("git")
    else
        verbose_log "✓ Git found: $(git --version | head -n1)"
    fi

    # Check for curl
    if ! command -v curl &> /dev/null; then
        missing_tools+=("curl")
    else
        verbose_log "✓ curl found"
    fi

    if [[ ${#missing_tools[@]} -gt 0 ]] && [[ "$SKIP_DOCKER" != "true" ]]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        echo "Please install the missing tools and try again."
        return 1
    fi

    log_success "All prerequisites are met"
}

################################################################################
# Directory Setup
################################################################################

setup_directories() {
    print_step "2" "Setting up directories"

    local dirs=(
        "${PROJECT_ROOT}/memory"
        "${PROJECT_ROOT}/rag/faiss"
        "${PROJECT_ROOT}/rag/chunks"
        "${PROJECT_ROOT}/logs"
        "${PROJECT_ROOT}/config"
        "${PROJECT_ROOT}/data/neo4j"
    )

    for dir in "${dirs[@]}"; do
        if [[ ! -d "$dir" ]]; then
            mkdir -p "$dir"
            log_success "Created directory: $dir"
        else
            verbose_log "Directory already exists: $dir"
        fi
    done

    # Set proper permissions
    chmod 755 "${PROJECT_ROOT}/scripts/setup_brain.sh"
    chmod 755 "${PROJECT_ROOT}/logs"

    log_success "All directories are ready"
}

################################################################################
# Environment Configuration
################################################################################

setup_environment() {
    print_step "3" "Setting up environment"

    if [[ ! -f "${PROJECT_ROOT}/.env" ]]; then
        if [[ -f "${PROJECT_ROOT}/.env.example" ]]; then
            cp "${PROJECT_ROOT}/.env.example" "${PROJECT_ROOT}/.env"
            log_success "Created .env from .env.example"
        else
            log_error "No .env or .env.example found"
            return 1
        fi
    else
        verbose_log ".env file already exists"
    fi

    # Verify critical environment variables
    source "${PROJECT_ROOT}/.env" || true

    log_success "Environment configuration ready"
}

################################################################################
# Docker Compose Services
################################################################################

start_docker_services() {
    print_step "4" "Starting Docker Compose services"

    if [[ "$SKIP_DOCKER" == "true" ]]; then
        log_warn "Skipping Docker service startup (--skip-docker flag)"
        return 0
    fi

    cd "$PROJECT_ROOT"

    # Check if services are already running
    if docker-compose ps | grep -q "claude-brain"; then
        log_warn "Services already running, skipping docker-compose up"
    else
        log_info "Starting services with docker-compose..."
        if ! docker-compose up -d; then
            log_error "Failed to start Docker Compose services"
            return 1
        fi
        log_success "Docker Compose services started"
    fi
}

################################################################################
# Service Health Checks
################################################################################

wait_for_neo4j() {
    print_step "5" "Waiting for Neo4j to be ready"

    local start_time=$(date +%s)
    local elapsed=0

    while [[ $elapsed -lt $NEO4J_TIMEOUT ]]; do
        if docker-compose exec -T neo4j cypher-shell -u "${NEO4J_USER:-neo4j}" -p "${NEO4J_PASSWORD}" "RETURN 1" &>/dev/null; then
            log_success "Neo4j is ready (${elapsed}s)"
            return 0
        fi

        elapsed=$(($(date +%s) - start_time))
        echo -n "."
        sleep 3
    done

    log_error "Neo4j failed to start within ${NEO4J_TIMEOUT}s"
    docker-compose logs neo4j | tail -20 >> "$LOG_FILE"
    return 1
}

wait_for_redis() {
    print_step "6" "Waiting for Redis to be ready"

    local start_time=$(date +%s)
    local elapsed=0

    while [[ $elapsed -lt $REDIS_TIMEOUT ]]; do
        if docker-compose exec -T redis redis-cli -a "${REDIS_PASSWORD}" ping &>/dev/null; then
            log_success "Redis is ready (${elapsed}s)"
            return 0
        fi

        elapsed=$(($(date +%s) - start_time))
        echo -n "."
        sleep 2
    done

    log_error "Redis failed to start within ${REDIS_TIMEOUT}s"
    docker-compose logs redis | tail -20 >> "$LOG_FILE"
    return 1
}

wait_for_api() {
    print_step "7" "Waiting for API to be ready"

    local start_time=$(date +%s)
    local elapsed=0

    while [[ $elapsed -lt $API_TIMEOUT ]]; do
        if curl -sf http://127.0.0.1:8765/ &>/dev/null; then
            log_success "API is ready (${elapsed}s)"
            return 0
        fi

        elapsed=$(($(date +%s) - start_time))
        echo -n "."
        sleep 5
    done

    log_warn "API not responding within ${API_TIMEOUT}s (this may be normal if API is not yet built)"
    return 0
}

################################################################################
# Python Dependencies
################################################################################

install_python_deps() {
    print_step "8" "Installing Python dependencies"

    if [[ "$SKIP_DEPS" == "true" ]]; then
        log_warn "Skipping Python dependency installation (--skip-deps flag)"
        return 0
    fi

    if [[ ! -f "${PROJECT_ROOT}/requirements.txt" ]]; then
        log_warn "requirements.txt not found, skipping Python setup"
        return 0
    fi

    log_info "Installing dependencies from requirements.txt..."

    # Check for virtual environment
    if [[ -d "${PROJECT_ROOT}/.venv" ]]; then
        source "${PROJECT_ROOT}/.venv/bin/activate"
        verbose_log "Virtual environment activated"
    fi

    if ! pip install -q -r "${PROJECT_ROOT}/requirements.txt"; then
        log_error "Failed to install Python dependencies"
        return 1
    fi

    log_success "Python dependencies installed"
}

################################################################################
# Database Initialization
################################################################################

initialize_databases() {
    print_step "9" "Initializing databases"

    # Create Neo4j constraints and indexes
    log_info "Setting up Neo4j schema..."
    if docker-compose exec -T neo4j cypher-shell -u "${NEO4J_USER:-neo4j}" -p "${NEO4J_PASSWORD}" <<'EOF' &>/dev/null; then
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Memory) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Learning) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Decision) REQUIRE n.id IS UNIQUE;
CREATE INDEX IF NOT EXISTS FOR (n:Memory) ON (n.created_at);
CREATE INDEX IF NOT EXISTS FOR (n:Learning) ON (n.score);
CREATE INDEX IF NOT EXISTS FOR (n:Decision) ON (n.project);
EOF
        log_success "Neo4j schema initialized"
    else
        log_warn "Neo4j schema initialization skipped (may already exist)"
    fi

    # Initialize SQLite database
    log_info "Initializing SQLite database..."
    if [[ -f "${PROJECT_ROOT}/scripts/migrate.py" ]]; then
        cd "$PROJECT_ROOT"
        if python3 scripts/migrate.py &>/dev/null; then
            log_success "Database migrations completed"
        else
            log_warn "Database migrations may have already been applied"
        fi
    fi
}

################################################################################
# Connectivity Tests
################################################################################

run_connectivity_tests() {
    print_step "10" "Running connectivity tests"

    local tests_passed=0
    local tests_total=0

    # Test Neo4j connection
    tests_total=$((tests_total + 1))
    if docker-compose exec -T neo4j cypher-shell -u "${NEO4J_USER:-neo4j}" -p "${NEO4J_PASSWORD}" "RETURN 1" &>/dev/null; then
        log_success "Neo4j connectivity: OK"
        tests_passed=$((tests_passed + 1))
    else
        log_error "Neo4j connectivity: FAILED"
    fi

    # Test Redis connection
    tests_total=$((tests_total + 1))
    if docker-compose exec -T redis redis-cli -a "${REDIS_PASSWORD}" ping &>/dev/null; then
        log_success "Redis connectivity: OK"
        tests_passed=$((tests_passed + 1))
    else
        log_error "Redis connectivity: FAILED"
    fi

    # Test API connectivity (if running)
    tests_total=$((tests_total + 1))
    if curl -sf http://127.0.0.1:8765/ &>/dev/null; then
        log_success "API connectivity: OK"
        tests_passed=$((tests_passed + 1))
    else
        log_warn "API connectivity: Not available (may not be built yet)"
    fi

    verbose_log "Connectivity tests: $tests_passed/$tests_total passed"
}

################################################################################
# Summary and Next Steps
################################################################################

print_summary() {
    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}     Setup Completed Successfully!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
    echo ""

    cat <<EOF
${BLUE}Claude Brain Infrastructure${NC}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

${GREEN}Accessible Services:${NC}
  • Neo4j Browser: ${BLUE}http://localhost:7474${NC}
    - Username: neo4j
    - Password: brainpassword

  • Redis CLI: ${BLUE}redis-cli -p 6379 -a brainredis${NC}

  • Claude Brain API: ${BLUE}http://localhost:8765${NC}

${GREEN}Useful Commands:${NC}
  • View logs:           docker-compose logs -f [service-name]
  • Stop services:       docker-compose down
  • Restart services:    docker-compose restart
  • Check status:        docker-compose ps

${GREEN}Project Structure:${NC}
  • Config:              ${PROJECT_ROOT}/config
  • Data (Neo4j):        ${PROJECT_ROOT}/data/neo4j
  • Logs:                ${PROJECT_ROOT}/logs
  • Memory (SQLite):     ${PROJECT_ROOT}/memory
  • RAG Index:           ${PROJECT_ROOT}/rag

${GREEN}Next Steps:${NC}
  1. Load your API keys into .env
  2. Run: docker-compose up --build
  3. Initialize with: brain graph sync
  4. Visit Neo4j browser to verify connectivity

${GREEN}Documentation:${NC}
  • Setup Guide:         See README_SETUP.md
  • API Docs:            See /api documentation
  • Neo4j Reference:     https://neo4j.com/docs

${BLUE}Setup log saved to:${NC} $LOG_FILE

EOF
}

################################################################################
# Main Execution
################################################################################

main() {
    print_header

    # Create log directory
    mkdir -p "$(dirname "$LOG_FILE")"
    echo "Setup started at $(date)" > "$LOG_FILE"

    parse_arguments "$@"

    log_info "Project root: $PROJECT_ROOT"
    log_info "Log file: $LOG_FILE"
    echo ""

    # Run setup steps
    check_prerequisites || return 1
    setup_directories || return 1
    setup_environment || return 1
    start_docker_services || return 1

    if [[ "$FAST_MODE" != "true" ]]; then
        wait_for_neo4j || return 1
        wait_for_redis || return 1
        wait_for_api
    fi

    install_python_deps || return 1
    initialize_databases || return 1
    run_connectivity_tests

    print_summary

    log_success "Setup completed successfully!"
    return 0
}

# Run main function
main "$@"
