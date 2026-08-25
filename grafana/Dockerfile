# Bakes the datasource/dashboard provisioning into the image instead of two
# relative bind mounts (./grafana/provisioning, ./grafana/dashboards). See
# db/Dockerfile's comment -- same reasoning: build-context directories are
# reliably present under every deployment method (plain `docker compose`,
# Portainer git-based stacks, etc.), relative host-path bind mounts to
# arbitrary repo subdirectories are not.
FROM grafana/grafana-oss:11.2.0

COPY provisioning/ /etc/grafana/provisioning/
COPY dashboards/ /var/lib/grafana/dashboards/
