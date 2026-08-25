# Bakes the schema init script into the image instead of relying on a
# relative bind mount (./db/init:/docker-entrypoint-initdb.d). Some
# environments -- notably Portainer git-based stacks -- don't reliably check
# out every directory in the repo beyond what's needed as a build context,
# which left this mount failing with "does not exist" even though the repo
# on disk had the file. Baking it in means it only has to survive as part of
# this Dockerfile's own build context (./db), which every deployment method
# handles correctly.
FROM timescale/timescaledb:2.16.1-pg16

COPY init/ /docker-entrypoint-initdb.d/
