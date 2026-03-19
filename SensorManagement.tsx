# GridIQ — Nginx Configuration
# Serves the React frontend and proxies API + WebSocket to FastAPI

worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /tmp/nginx.pid;

events {
    worker_connections 1024;
    use epoll;
    multi_accept on;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] '
                    '"$request" $status $body_bytes_sent '
                    '"$http_referer" "$http_user_agent"';
    access_log /var/log/nginx/access.log main;

    # Performance
    sendfile           on;
    tcp_nopush         on;
    tcp_nodelay        on;
    keepalive_timeout  65;
    gzip               on;
    gzip_types         text/plain text/css application/json
                       application/javascript text/xml application/xml
                       application/xml+rss text/javascript;

    # Security headers
    add_header X-Frame-Options       "SAMEORIGIN"   always;
    add_header X-XSS-Protection      "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff"      always;
    add_header Referrer-Policy       "strict-origin-when-cross-origin" always;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=60r/m;
    limit_req_zone $binary_remote_addr zone=auth:10m rate=10r/m;

    # Upstream: FastAPI backend
    upstream gridiq_api {
        server api:8000;
        keepalive 32;
    }

    # ── HTTP → HTTPS redirect ────────────────────────────────────────────────
    server {
        listen 80;
        server_name _;

        # Let's Encrypt challenge (for cert renewal)
        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        # Redirect everything else to HTTPS
        location / {
            return 301 https://$host$request_uri;
        }
    }

    # ── HTTPS main server ────────────────────────────────────────────────────
    server {
        listen 443 ssl http2;
        server_name GRIDIQ_DOMAIN;  # replaced by deploy script

        # SSL certificates (Let's Encrypt via certbot)
        ssl_certificate     /etc/letsencrypt/live/GRIDIQ_DOMAIN/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/GRIDIQ_DOMAIN/privkey.pem;

        # Modern SSL config (Mozilla Intermediate)
        ssl_protocols             TLSv1.2 TLSv1.3;
        ssl_ciphers               ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
        ssl_prefer_server_ciphers off;
        ssl_session_cache         shared:SSL:10m;
        ssl_session_timeout       1d;
        ssl_stapling              on;
        ssl_stapling_verify       on;

        # HSTS (1 year)
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

        # ── React frontend (static files) ───────────────────────────────────
        root /usr/share/nginx/html;
        index index.html;

        # Cache static assets aggressively (hashed filenames from Vite)
        location ~* \.(js|css|png|jpg|svg|ico|woff2?)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
            try_files $uri =404;
        }

        # React Router — all non-API routes serve index.html
        location / {
            try_files $uri $uri/ /index.html;
            add_header Cache-Control "no-cache";
        }

        # ── API proxy ────────────────────────────────────────────────────────
        location /api/ {
            limit_req zone=api burst=20 nodelay;

            proxy_pass         http://gridiq_api;
            proxy_http_version 1.1;
            proxy_set_header   Host              $host;
            proxy_set_header   X-Real-IP         $remote_addr;
            proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
            proxy_set_header   X-Forwarded-Proto $scheme;
            proxy_read_timeout 60s;
            proxy_send_timeout 60s;
        }

        # ── WebSocket proxy ──────────────────────────────────────────────────
        location /api/v1/ws/ {
            proxy_pass         http://gridiq_api;
            proxy_http_version 1.1;
            proxy_set_header   Upgrade    $http_upgrade;
            proxy_set_header   Connection "upgrade";
            proxy_set_header   Host       $host;
            proxy_read_timeout 86400s;   # 24h — keep WS alive
            proxy_send_timeout 86400s;
        }

        # ── API docs (restrict to internal if needed) ────────────────────────
        location ~ ^/(docs|redoc|openapi.json) {
            proxy_pass http://gridiq_api;
            proxy_set_header Host $host;
        }
    }
}
