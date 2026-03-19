# ── Python ────────────────────────────────────────────────────
__pycache__/
*.py[cod]
*.pyo
*.pyd
.Python
*.egg-info/
dist/
build/
.eggs/
venv/
.venv/
env/
*.egg
pip-wheel-metadata/

# ── Environment / secrets ─────────────────────────────────────
.env
.env.local
.env.*.local
config/.env
!config/.env.example
!frontend/.env.example

# ── ML models (too large for git — use Git LFS or S3) ────────
ml_models/
*.pt
*.pkl
*.h5
*.onnx

# ── Database ──────────────────────────────────────────────────
*.db
*.sqlite
*.sqlite3

# ── Logs & reports ────────────────────────────────────────────
*.log
logs/
reports/

# ── Frontend ──────────────────────────────────────────────────
node_modules/
frontend/dist/
frontend/.vite/
frontend/coverage/
*.local

# ── OS ────────────────────────────────────────────────────────
.DS_Store
Thumbs.db
desktop.ini

# ── IDE ───────────────────────────────────────────────────────
.vscode/
.idea/
*.swp
*.swo

# ── Docker ────────────────────────────────────────────────────
docker-compose.override.yml

# ── Test coverage ─────────────────────────────────────────────
.coverage
htmlcov/
.pytest_cache/
