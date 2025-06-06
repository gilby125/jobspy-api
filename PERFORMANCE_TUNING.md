# Performance Tuning

## Caching
- Adjust `CACHE_EXPIRY` via env var.
- Use Redis by mounting external cache.

## Concurrency
- Increase FastAPI workers: `uvicorn --workers 4`.
- Use Gunicorn with Uvicorn workers in production.

## Logging
- Set `LOG_LEVEL=INFO` or `DEBUG` as needed.
- Rotate logs by mounting a log driver.

## Monitoring
- Expose `/metrics` with Prometheus.claude
