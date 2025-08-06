# Installation Guide

## Quick Start

### 1. Install PostgreSQL (15 or higher)
```bash
# Ubuntu/Debian
sudo apt install postgresql-15 postgresql-contrib-15

# macOS
brew install postgresql@15

# Windows: Download from postgresql.org
```

### 2. Install Python Dependencies
```bash
pip install 'psycopg[binary]>=3.1'
```

### 3. Setup PostgreSQL User
```bash
sudo -u postgres createuser -P genealogy_user
sudo -u postgres psql -c "ALTER USER genealogy_user CREATEDB;"
```

### 4. Configure Connection
Create `connection_info.txt` in the addon directory:
```ini
host = localhost
port = 5432
user = genealogy_user
password = YourPassword
database_mode = monolithic
shared_database_name = gramps_monolithic
```

### 5. Install in Gramps
1. Copy this folder to: `~/.local/share/gramps/gramps60/plugins/PostgreSQLEnhanced/`
2. Restart Gramps
3. Create new tree with "PostgreSQL Enhanced" backend

## Documentation

- Full setup guide: `docs/guides/SETUP_GUIDE.md`
- Configuration guide: `docs/guides/DATABASE_CONFIGURATION_GUIDE.md`
- Troubleshooting: `docs/troubleshooting/`

## Support

- GitHub Issues: https://github.com/glamberson/gramps-postgresql-enhanced/issues
- Email: greg@aigenealogyinsights.com