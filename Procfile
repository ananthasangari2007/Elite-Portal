web: python -m app.cli db-upgrade && uvicorn main:app --host 0.0.0.0 --port ${PORT:-5000} --proxy-headers --forwarded-allow-ips "*"
