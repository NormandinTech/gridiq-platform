# GridIQ — Deployment Guide

## Live in 15 minutes on any VPS

### Step 1 — Pick a server

Any of these work. All have free trial credits:

| Provider | Spec | Cost | Credit |
|----------|------|------|--------|
| **DigitalOcean** | 2 vCPU / 4 GB / 80 GB | $24/mo | $200 free (60 days) |
| **Hetzner** | 2 vCPU / 4 GB / 40 GB | €4.5/mo | Best value in EU |
| **Linode (Akamai)** | 2 vCPU / 4 GB / 80 GB | $24/mo | $100 free |
| **Vultr** | 2 vCPU / 4 GB / 80 GB | $24/mo | $250 free |
| **AWS EC2** | t3.medium | ~$30/mo | 1 year free tier |

**Pick Ubuntu 22.04 LTS** when creating the server.

---

### Step 2 — Point your domain

In your domain registrar (Namecheap, GoDaddy, Cloudflare, etc.):

```
A record:   gridiq.yourdomain.com  →  YOUR_SERVER_IP
```

Wait 2–5 minutes for DNS to propagate. Test with:
```bash
ping gridiq.yourdomain.com
```

---

### Step 3 — Deploy (one command)

SSH into your server, then:

```bash
# Clone your repo
git clone https://github.com/YOUR_USERNAME/gridiq-platform.git
cd gridiq-platform

# Run the deploy script
chmod +x deployment/deploy.sh
sudo ./deployment/deploy.sh
```

The script will:
1. Install Docker + Docker Compose
2. Configure the firewall
3. Ask for your domain and email
4. Generate secure passwords automatically
5. Build and start all services
6. Run database migrations
7. Get a free SSL certificate from Let's Encrypt
8. Set up nightly auto-updates

**Total time: ~10 minutes**

---

### What's running after deploy

```
https://yourdomain.com          → React dashboard
https://yourdomain.com/docs     → API documentation (Swagger UI)
https://yourdomain.com/api/v1/  → REST API

Internally (not exposed to internet):
  TimescaleDB    localhost:5432
  Redis          localhost:6379
```

---

### Useful commands after deploy

```bash
# View live API logs
docker compose -f docker-compose.prod.yml logs -f api

# View all service status
docker compose -f docker-compose.prod.yml ps

# Restart the API
docker compose -f docker-compose.prod.yml restart api

# Open a database shell
docker compose -f docker-compose.prod.yml exec db psql -U gridiq gridiq_db

# Check TimescaleDB hypertables
docker compose -f docker-compose.prod.yml exec db psql -U gridiq gridiq_db \
  -c "SELECT hypertable_name, num_chunks FROM timescaledb_information.hypertables;"

# Run database migrations after a code update
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head

# Full redeploy after pushing new code
git pull
docker compose -f docker-compose.prod.yml up -d --build

# Backup the database
docker compose -f docker-compose.prod.yml exec db \
  pg_dump -U gridiq gridiq_db | gzip > backup_$(date +%Y%m%d).sql.gz
```

---

### Connecting real SCADA hardware

Once deployed, connect real assets by editing `config/.env`:

```bash
# Disable simulation
SIMULATE_TELEMETRY=false

# Add your RTU/SCADA endpoints
MODBUS_TARGETS=192.168.1.100:502:1,192.168.1.101:502:1
DNP3_OUTSTATION_ADDRESS=10
IEC61850_SERVER_HOST=192.168.1.200
```

Then restart:
```bash
docker compose -f docker-compose.prod.yml restart api
```

---

### Database schema

The database uses TimescaleDB for the telemetry tables.
This gives you automatic time-partitioning and compression.

```sql
-- Check your data after running the platform for a while
SELECT
  time_bucket('1 hour', timestamp) as hour,
  asset_id,
  avg(active_power_mw) as avg_mw,
  count(*) as readings
FROM telemetry_readings
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY hour, asset_id
ORDER BY hour DESC;
```

---

### Scaling up

When you need more capacity:

**Vertical scale** — upgrade the VPS to 4 vCPU / 8 GB RAM.
Most municipal utilities will fit here for years.

**Horizontal scale** — add a read replica for the database:
```bash
# In docker-compose.prod.yml, add:
db-replica:
  image: timescale/timescaledb:latest-pg16
  environment:
    POSTGRES_REPLICA_MODE: replica
    POSTGRES_PRIMARY_HOST: db
```

**TimescaleDB Cloud** — for large IOUs with 100K+ assets,
move the database to managed TimescaleDB at cloud.timescale.com.
Change `DATABASE_URL` and everything else stays the same.

---

### SSL renewal

Certificates renew automatically. The certbot container checks every 12 hours
and renews when within 30 days of expiry.

To manually force renewal:
```bash
docker compose -f docker-compose.prod.yml run --rm certbot \
  certbot renew --force-renewal
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

---

### Estimated monthly costs

| Component | Cost |
|-----------|------|
| VPS (2vCPU/4GB) | $24/mo |
| Domain name | ~$1/mo |
| SSL certificate | Free (Let's Encrypt) |
| **Total** | **~$25/mo** |

For a utility paying $48K/year for the Starter tier,
your server cost is 0.6% of revenue. Very healthy margin.
