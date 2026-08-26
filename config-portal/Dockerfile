# Small, stateless service -- no volumes, no bind mounts, so none of the
# Synology permission/ACL issues that affect Grafana and TimescaleDB apply
# here (see docs/NAS.md). Runs as the image's default non-root user.
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

EXPOSE 8080
CMD ["python", "app.py"]
