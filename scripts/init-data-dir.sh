#!/usr/bin/env sh
# Creates the host directories docker-compose.yml's bind mounts expect to
# already exist (${CURB_DATA_DIR}/pgdata and ${CURB_DATA_DIR}/grafana).
#
# Why this is a separate manual step instead of something the stack creates
# itself on startup: modern Docker Compose deliberately refuses to bind-mount
# a host path that doesn't exist, rather than silently creating an empty
# directory there. That's a safety feature, not a bug -- for a database data
# directory specifically, silently creating an empty folder on a typo'd path
# is worse than failing loudly, since it would look like a successful deploy
# while quietly starting from a blank database instead of mounting your real
# data. So the fix is to run this once before your first deploy, not to make
# the failure mode quieter.
#
# Usage:
#   ./scripts/init-data-dir.sh                       # reads CURB_DATA_DIR from .env, defaults to ./data
#   ./scripts/init-data-dir.sh /absolute/nas/path     # explicit path -- use this for Portainer/NAS deploys,
#                                                      # where CURB_DATA_DIR is set via Portainer's UI, not .env
#                                                      # (must match that value exactly)

set -eu

if [ -n "${1:-}" ]; then
  DATA_DIR="$1"
elif [ -f .env ] && grep -qE '^CURB_DATA_DIR=' .env; then
  DATA_DIR=$(grep -E '^CURB_DATA_DIR=' .env | tail -n1 | cut -d= -f2-)
else
  DATA_DIR="./data"
fi

DATA_DIR="${DATA_DIR:-./data}"

mkdir -p "$DATA_DIR/pgdata" "$DATA_DIR/grafana"
echo "Created:"
echo "  $DATA_DIR/pgdata"
echo "  $DATA_DIR/grafana"
echo
echo "No chown needed -- both timescaledb and grafana now manage their own"
echo "data directory permissions at container startup (grafana runs as root"
echo "specifically to avoid host-side permission/ACL quirks -- see"
echo "docs/NAS.md if you want the details or to lock that back down)."
echo
echo "Make sure CURB_DATA_DIR is set to exactly: $DATA_DIR"
echo "(in .env for plain docker compose, or in the stack's Environment"
echo "variables in Portainer)."
