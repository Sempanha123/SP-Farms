# Diagnostics

SP-Farms writes newline-delimited JSON logs to the platform user log directory. Each entry contains an ISO 8601 UTC timestamp, severity, logger name, and message. Files rotate at 5 MB with five retained backups by default.

Use module loggers through `get_logger("module.name")`. Redaction removes authorization headers, bearer tokens, passwords, cookies, token/secret values, and recovery codes before structured output. Do not include raw secret objects in log metadata.

A support bundle contains:

- application, Python, and operating-system versions;
- database and log paths;
- provider availability summaries;
- a redacted copy of the current application log.

Bundles intentionally exclude environment variables, local configuration files, vault data, credentials, and database contents. Review a bundle before sharing it.

Non-secret configuration can be stored in a TOML file:

```toml
[sp_farms]
environment = "production"
log_level = "INFO"
database_path = "C:/path/to/sp_farms.db"
log_path = "C:/path/to/sp_farms.log"
log_max_bytes = 5000000
log_backup_count = 5
```

Set `SP_FARMS_CONFIG` to select that file. Individual `SP_FARMS_ENV`, `SP_FARMS_LOG_LEVEL`, `SP_FARMS_DATABASE_PATH`, `SP_FARMS_LOG_PATH`, `SP_FARMS_LOG_MAX_BYTES`, and `SP_FARMS_LOG_BACKUP_COUNT` environment variables override file values. Secrets must remain in the secure vault, never this file.
