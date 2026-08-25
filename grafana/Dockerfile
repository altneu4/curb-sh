# Bakes the datasource/dashboard provisioning into the image instead of two
# relative bind mounts (./grafana/provisioning, ./grafana/dashboards). See
# db/Dockerfile's comment -- same reasoning: build-context directories are
# reliably present under every deployment method (plain `docker compose`,
# Portainer git-based stacks, etc.), relative host-path bind mounts to
# arbitrary repo subdirectories are not.
#
# Dashboard JSON goes to /etc/grafana/dashboards, NOT the more conventional
# /var/lib/grafana/dashboards -- docker-compose.yml bind-mounts the whole of
# /var/lib/grafana for data persistence (see docs/NAS.md), and a bind mount
# entirely replaces whatever the image put there. Baking the dashboard
# under /var/lib/grafana would just get shadowed by the (empty) host
# directory the moment the container starts. /etc/grafana/provisioning
# isn't bind-mounted, so /etc/grafana/dashboards alongside it is safe, and
# dashboard.yml's `path:` below is pointed there to match.
FROM grafana/grafana-oss:11.2.0

COPY provisioning/ /etc/grafana/provisioning/
COPY dashboards/ /etc/grafana/dashboards/
