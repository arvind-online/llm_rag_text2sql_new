Walkthrough: Switchable PostgreSQL / ClickHouse Support
What Changed
config.py
New db_type field: "postgres" (default) or "clickhouse"
ClickHouse credentials: ch_host, ch_port, ch_user, ch_password, ch_database
clickhouse_url
 — builds clickhouse+http:// URL
active_database_url
 — returns Postgres or ClickHouse URL based on db_type
db_dialect
 — returns "PostgreSQL" or "ClickHouse" for prompts
text2sql_agent.py
Dual-dialect prompts: POSTGRES_SQL_RULES vs CLICKHOUSE_SQL_RULES injected dynamically
Engine: uses settings.active_database_url instead of hardcoded PG URL
Schema introspection: skips PK constraint introspection for ClickHouse
Metadata: includes db_type; sources show "Database (ClickHouse)" or "Database (PostgreSQL)"
.env.example
 / 
.env
Added DB_TYPE=postgres switch
Added ClickHouse credential placeholders
requirements.txt
Added clickhouse-driver==0.2.9 and clickhouse-sqlalchemy==0.3.5
testdb_conn.py
Prints active database type on startup
How to Switch Databases
env
# In .env — set to "postgres" or "clickhouse"
DB_TYPE=clickhouse
# Fill in ClickHouse credentials
CH_HOST=your-clickhouse-host
CH_PORT=8123
CH_USER=default
CH_PASSWORD=your-password
CH_DATABASE=your-database
Then restart the server. No code changes needed.

Validation
✅ All modified files pass py_compile
✅ Committed to feature/clickhouse branch (bb88972)
⚠️ Install new deps: pip install clickhouse-sqlalchemy clickhouse-driver