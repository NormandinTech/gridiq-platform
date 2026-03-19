# GridIQ — Production Environment Variables
# Copy to .env.prod and fill in ALL values before deploying
# NEVER commit this file to git — it's in .gitignore

# ── Domain ────────────────────────────────────────────────────────────────────
DOMAIN=gridiq.yourdomain.com        # Your actual domain (used for SSL + CORS)

# ── Database ──────────────────────────────────────────────────────────────────
DB_NAME=gridiq_db
DB_USER=gridiq
DB_PASSWORD=CHANGE_THIS_STRONG_PASSWORD_32_CHARS_MIN

# ── Redis ─────────────────────────────────────────────────────────────────────
REDIS_PASSWORD=CHANGE_THIS_REDIS_PASSWORD

# ── Security ──────────────────────────────────────────────────────────────────
# Generate with: python3 -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY=GENERATE_WITH_COMMAND_ABOVE

# ── Telemetry simulation (set false when connecting real SCADA) ───────────────
SIMULATE_TELEMETRY=true

# ── Optional integrations ─────────────────────────────────────────────────────
OPENWEATHER_API_KEY=           # openweathermap.org free tier
SLACK_WEBHOOK_URL=             # for SOC alert notifications
SMTP_HOST=smtp.gmail.com
SMTP_USERNAME=
SMTP_PASSWORD=
ALERT_EMAIL_RECIPIENTS=ops@yourcompany.com
