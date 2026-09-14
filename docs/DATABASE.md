# Database

SP-Farms stores local application data in SQLite through SQLAlchemy 2.x. Every connection enables WAL journaling, foreign-key enforcement, normal synchronous mode, and a 30-second busy timeout.

Persistent entities use UUID string identities plus `created_at`, `updated_at`, and nullable `archived_at` timestamps. Application services transact through the unit-of-work port; UI code never opens sessions.

Alembic migrations run at application startup. A database already carrying an older Alembic revision is copied beside itself with a UTC timestamp and `.bak` suffix before upgrade. Clean installs and already-current databases do not create unnecessary backups.

Run migrations manually with the repository-local interpreter:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Migration downgrades are for development and recovery testing. Production recovery should restore a verified backup rather than destructively downgrading live data.
