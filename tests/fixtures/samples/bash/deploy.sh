#!/usr/bin/env bash
#
# deploy.sh - Deployment script for application services.
#
# Supports rolling deployments, health checks, and automatic rollback.
# Usage: ./deploy.sh [environment] [version]
#
# Environments: development, staging, production
# Example: ./deploy.sh staging v1.2.3
#

set -euo pipefail

# ==============================================================================
# Configuration
# ==============================================================================

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly LOG_FILE="/var/log/deploy/$(date +%Y%m%d_%H%M%S).log"
readonly DEPLOY_USER="${DEPLOY_USER:-deployer}"
readonly HEALTH_CHECK_RETRIES=10
readonly HEALTH_CHECK_INTERVAL=5
readonly ROLLBACK_ON_FAILURE=true

# Color codes for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# ==============================================================================
# Logging Functions
# ==============================================================================

log_info() {
    local message="$1"
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') $message"
    echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') $message" >> "$LOG_FILE"
}

log_success() {
    local message="$1"
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') $message"
    echo "[SUCCESS] $(date '+%Y-%m-%d %H:%M:%S') $message" >> "$LOG_FILE"
}

log_warning() {
    local message="$1"
    echo -e "${YELLOW}[WARNING]${NC} $(date '+%Y-%m-%d %H:%M:%S') $message"
    echo "[WARNING] $(date '+%Y-%m-%d %H:%M:%S') $message" >> "$LOG_FILE"
}

log_error() {
    local message="$1"
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') $message" >&2
    echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') $message" >> "$LOG_FILE"
}

# ==============================================================================
# Utility Functions
# ==============================================================================

# Validate the deployment environment
validate_environment() {
    local env="$1"

    case "$env" in
        development|staging|production)
            log_info "Environment validated: $env"
            return 0
            ;;
        *)
            log_error "Invalid environment: $env"
            log_error "Valid options: development, staging, production"
            return 1
            ;;
    esac
}

# Check if required tools are installed
check_dependencies() {
    local required_tools=("docker" "kubectl" "jq" "curl")
    local missing_tools=()

    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done

    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        return 1
    fi

    log_info "All required tools are available"
    return 0
}

# Wait for service to become healthy
wait_for_healthy() {
    local service_url="$1"
    local retries="${2:-$HEALTH_CHECK_RETRIES}"
    local interval="${3:-$HEALTH_CHECK_INTERVAL}"

    log_info "Waiting for service to become healthy: $service_url"

    for ((i=1; i<=retries; i++)); do
        local status_code

        status_code=$(curl -s -o /dev/null -w "%{http_code}" "$service_url/health" || echo "000")

        if [[ "$status_code" == "200" ]]; then
            log_success "Service is healthy after $i attempt(s)"
            return 0
        fi

        log_warning "Health check attempt $i/$retries failed (status: $status_code)"
        sleep "$interval"
    done

    log_error "Service failed to become healthy after $retries attempts"
    return 1
}

# ==============================================================================
# Deployment Functions
# ==============================================================================

# Pull and tag the deployment image
prepare_image() {
    local version="$1"
    local registry="${DOCKER_REGISTRY:-registry.example.com}"
    local image="${registry}/app:${version}"

    log_info "Pulling image: $image"

    if ! docker pull "$image"; then
        log_error "Failed to pull image: $image"
        return 1
    fi

    log_success "Image prepared: $image"
    return 0
}

# Deploy to Kubernetes cluster
deploy_to_kubernetes() {
    local environment="$1"
    local version="$2"
    local namespace="app-${environment}"

    log_info "Deploying version $version to $environment"

    # Update the deployment image
    if ! kubectl set image deployment/app \
        "app=registry.example.com/app:${version}" \
        -n "$namespace"; then
        log_error "Failed to update deployment image"
        return 1
    fi

    # Wait for rollout to complete
    if ! kubectl rollout status deployment/app \
        -n "$namespace" \
        --timeout=300s; then
        log_error "Deployment rollout failed"
        return 1
    fi

    log_success "Deployment completed successfully"
    return 0
}

# Rollback to previous version
rollback() {
    local environment="$1"
    local namespace="app-${environment}"

    log_warning "Initiating rollback for $environment"

    if ! kubectl rollout undo deployment/app -n "$namespace"; then
        log_error "Rollback failed!"
        return 1
    fi

    if ! kubectl rollout status deployment/app \
        -n "$namespace" \
        --timeout=300s; then
        log_error "Rollback did not complete successfully"
        return 1
    fi

    log_success "Rollback completed successfully"
    return 0
}

# ==============================================================================
# Main Entry Point
# ==============================================================================

main() {
    local environment="${1:-staging}"
    local version="${2:-latest}"

    # Create log directory
    mkdir -p "$(dirname "$LOG_FILE")"

    log_info "=========================================="
    log_info "Starting deployment"
    log_info "Environment: $environment"
    log_info "Version: $version"
    log_info "=========================================="

    # Pre-deployment checks
    validate_environment "$environment" || exit 1
    check_dependencies || exit 1

    # Deployment
    prepare_image "$version" || exit 1

    if ! deploy_to_kubernetes "$environment" "$version"; then
        if [[ "$ROLLBACK_ON_FAILURE" == "true" ]]; then
            log_warning "Deployment failed, attempting rollback..."
            rollback "$environment" || exit 1
        fi
        exit 1
    fi

    # Post-deployment health check
    local service_url
    service_url=$(kubectl get svc app -n "app-${environment}" -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

    if ! wait_for_healthy "http://${service_url}:8080"; then
        if [[ "$ROLLBACK_ON_FAILURE" == "true" ]]; then
            log_warning "Health check failed, attempting rollback..."
            rollback "$environment" || exit 1
        fi
        exit 1
    fi

    log_success "=========================================="
    log_success "Deployment completed successfully!"
    log_success "Environment: $environment"
    log_success "Version: $version"
    log_success "=========================================="
}

# Run main function with all arguments
main "$@"
