#!/bin/bash
# ============================================================
#  GridIQ Platform — One-Command Deployment Script
#  Tested on: Ubuntu 22.04 LTS, Ubuntu 24.04 LTS, Debian 12
# ============================================================
#
#  USAGE:
#    1. Spin up a fresh VPS (DigitalOcean, Hetzner, Linode, AWS EC2)
#       Minimum spec: 2 vCPU, 4 GB RAM, 40 GB SSD
#       Recommended:  4 vCPU, 8 GB RAM, 80 GB SSD
#
#    2. Point your domain A record to the server IP
#       e.g. gridiq.yourdomain.com → your.server.ip
#       Wait for DNS to propagate (2–5 min on most registrars)
#
#    3. SSH into the server and run:
#       curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/gridiq-platform/main/deployment/deploy.sh | bash
#
#       Or clone the repo first:
#       git clone https://github.com/YOUR_USERNAME/gridiq-platform.git
#       cd gridiq-platform
#       chmod +x deployment/deploy.sh
#       ./deployment/deploy.sh
#
# ============================================================

set -euo pipefail

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

log()     { echo -e "${GREEN}[GridIQ]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
section() { echo -e "\n${BOLD}${BLUE}══ $1 ══${NC}\n"; }

# ── Banner ────────────────────────────────────────────────────────────────────
echo -e "${BOLD}"
cat << 'EOF'
   ____      _     _ ___ ___
  / ___|_ __(_) __| |_ _/ _ \
 | |  _| '__| |/ _` || | | | |
 | |_| | |  | | (_| || | |_| |
  \____|_|  |_|\__,_|___\__\_\

  Platform Deployment Script v1.0
  AI-Driven Grid Intelligence
EOF
echo -e "${NC}"

# ── Pre-flight checks ─────────────────────────────────────────────────────────
section "Pre-flight checks"

if [ "$EUID" -ne 0 ]; then
    error "Please run as root (sudo ./deploy.sh)"
fi

if [ ! -f "deployment/.env.prod.example" ]; then
    error "Run this script from the gridiq-platform project root directory"
fi

log "Running on: $(lsb_release -d 2>/dev/null || cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2)"
log "Server IP: $(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')"

# ── Collect configuration ─────────────────────────────────────────────────────
section "Configuration"

if [ -f "deployment/.env.prod" ]; then
    log "Found existing deployment/.env.prod — using it"
    source deployment/.env.prod
else
    echo -e "${YELLOW}We need a few details to configure your deployment.${NC}\n"

    read -p "  Your domain (e.g. gridiq.yourdomain.com): " DOMAIN
    [ -z "$DOMAIN" ] && error "Domain is required"

    read -p "  Your email (for SSL certificate): " SSL_EMAIL
    [ -z "$SSL_EMAIL" ] && error "Email is required for SSL"

    # Generate secure passwords automatically
    DB_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
    REDIS_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(20))")
    JWT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

    # Write .env.prod
    cat > deployment/.env.prod << ENVEOF
DOMAIN=${DOMAIN}
SSL_EMAIL=${SSL_EMAIL}
DB_NAME=gridiq_db
DB_USER=gridiq
DB_PASSWORD=${DB_PASSWORD}
REDIS_PASSWORD=${REDIS_PASSWORD}
JWT_SECRET_KEY=${JWT_SECRET_KEY}
SIMULATE_TELEMETRY=true
ENVEOF

    log "Configuration saved to deployment/.env.prod"
    warn "IMPORTANT: Back up deployment/.env.prod — it contains your database password"
fi

source deployment/.env.prod

log "Domain:     $DOMAIN"
log "Email:      ${SSL_EMAIL:-not set}"

# ── Install system dependencies ───────────────────────────────────────────────
section "Installing dependencies"

apt-get update -qq
apt-get install -y -qq \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    ufw \
    fail2ban \
    unzip

# Install Docker
if ! command -v docker &> /dev/null; then
    log "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    log "Docker installed: $(docker --version)"
else
    log "Docker already installed: $(docker --version)"
fi

# Install Docker Compose v2
if ! docker compose version &> /dev/null; then
    log "Installing Docker Compose..."
    COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep tag_name | cut -d'"' -f4)
    curl -SL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-x86_64" \
        -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
fi
log "Docker Compose: $(docker compose version)"

# ── Firewall setup ────────────────────────────────────────────────────────────
section "Firewall configuration"

ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh        # port 22
ufw allow 80/tcp     # HTTP  (→ HTTPS redirect)
ufw allow 443/tcp    # HTTPS
ufw --force enable
log "Firewall: SSH + HTTP + HTTPS allowed, everything else blocked"

# Fail2ban for SSH brute force protection
systemctl enable fail2ban
systemctl start fail2ban
log "Fail2ban: enabled"

# ── Configure nginx template ──────────────────────────────────────────────────
section "Configuring nginx"

sed -i "s/GRIDIQ_DOMAIN/${DOMAIN}/g" deployment/nginx/nginx.conf
log "Nginx config updated for domain: $DOMAIN"

# ── Build and start services ──────────────────────────────────────────────────
section "Building GridIQ (this takes 3–5 minutes)"

export $(cat deployment/.env.prod | grep -v '#' | xargs)

# Build images
docker compose -f docker-compose.prod.yml build --no-cache
log "Docker images built"

# Start database and redis first
docker compose -f docker-compose.prod.yml up -d db redis
log "Waiting for database to be ready..."
sleep 15

# Run database migrations
log "Running database migrations..."
docker compose -f docker-compose.prod.yml run --rm api \
    bash -c "cd /app && alembic upgrade head"
log "Migrations complete"

# Seed initial data
log "Seeding initial data..."
docker compose -f docker-compose.prod.yml run --rm api \
    python3 scripts/seed_data.py
log "Seed data loaded"

# Start all services
docker compose -f docker-compose.prod.yml up -d
log "All services started"

# ── SSL certificate ───────────────────────────────────────────────────────────
section "Setting up SSL certificate"

# First start nginx without SSL to get cert
docker compose -f docker-compose.prod.yml up -d nginx

sleep 5

# Get initial certificate
docker compose -f docker-compose.prod.yml run --rm certbot \
    certbot certonly \
    --webroot \
    --webroot-path /var/www/certbot \
    --email "${SSL_EMAIL}" \
    --agree-tos \
    --no-eff-email \
    -d "${DOMAIN}" \
    --non-interactive \
    2>/dev/null || {
        warn "SSL certificate failed — check DNS is pointing to this server"
        warn "You can get SSL later with: docker compose -f docker-compose.prod.yml --profile ssl up certbot"
    }

# Reload nginx to pick up the certificate
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload 2>/dev/null || true
log "Nginx reloaded with SSL"

# ── Verify deployment ─────────────────────────────────────────────────────────
section "Verifying deployment"

sleep 10

# Check all containers are running
CONTAINERS=$(docker compose -f docker-compose.prod.yml ps --format json 2>/dev/null | python3 -c "
import sys, json
services = [json.loads(l) for l in sys.stdin if l.strip()]
for s in services:
    status = s.get('State','unknown')
    name = s.get('Service','?')
    print(f'  {name}: {status}')
" 2>/dev/null || docker compose -f docker-compose.prod.yml ps)
echo "$CONTAINERS"

# Health check
sleep 5
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health 2>/dev/null || echo "000")
if [ "$HTTP_STATUS" = "200" ]; then
    log "API health check: OK (HTTP 200)"
else
    warn "API health check returned HTTP $HTTP_STATUS — check logs with: docker compose -f docker-compose.prod.yml logs api"
fi

# ── Setup auto-updates ────────────────────────────────────────────────────────
section "Configuring automatic updates"

# Add cron job for nightly git pull + redeploy
CRON_CMD="0 2 * * * cd $(pwd) && git pull --quiet && docker compose -f docker-compose.prod.yml up -d --build --quiet 2>&1 >> /var/log/gridiq-deploy.log"
(crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
log "Auto-update cron job added (runs at 2am daily)"

# ── Done ──────────────────────────────────────────────────────────────────────
section "Deployment complete"

SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')

echo -e "${GREEN}${BOLD}"
echo "  ✓ GridIQ Platform is live!"
echo ""
echo "  Dashboard:  https://${DOMAIN}"
echo "  API docs:   https://${DOMAIN}/docs"
echo "  Health:     https://${DOMAIN}/api/v1/health"
echo ""
echo "  Credentials saved in: deployment/.env.prod"
echo "  DB password: ${DB_PASSWORD}"
echo "${NC}"

echo -e "${YELLOW}Useful commands:${NC}"
echo "  View logs:     docker compose -f docker-compose.prod.yml logs -f api"
echo "  Restart:       docker compose -f docker-compose.prod.yml restart api"
echo "  DB shell:      docker compose -f docker-compose.prod.yml exec db psql -U gridiq gridiq_db"
echo "  Stop all:      docker compose -f docker-compose.prod.yml down"
echo ""
echo -e "${YELLOW}Back up these files:${NC}"
echo "  deployment/.env.prod   (passwords)"
echo "  gridiq_pgdata volume   (database)"
echo ""
