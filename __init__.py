# GridIQ — Alembic Configuration
# Database migration management for PostgreSQL + TimescaleDB

[alembic]
# Path to migration scripts
script_location = backend/db/migrations

# Template for new migration files
file_template = %%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d_%%(slug)s

# Timezone for migration timestamps
timezone = UTC

# Max length of migration slug
truncate_slug_length = 40

# SQLAlchemy URL — overridden by env.py reading from .env
sqlalchemy.url = postgresql+asyncpg://gridiq:password@localhost:5432/gridiq_db

# Logging configuration
[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
