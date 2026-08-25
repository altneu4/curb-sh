# Deploying on a NAS with Portainer

The default `docker-compose.yml` already bind-mounts TimescaleDB's and
Grafana's data directories to a real path on the host (`${CURB_DATA_DIR}`,
defaulting to `./data` next to the compose file) rather than opaque named
Docker volumes. That matters more on a NAS than it might elsewhere: your
NAS's own backup tooling -- Synology Hyper Backup, Btrfs/ZFS snapshots,
a plain rsync job -- expects to point at a real folder in your share
structure, not dig into Docker's internal volume storage (which often
lives on a different pool/mount than your user-facing shares and is
awkward to reach through the normal GUI). Named volumes already survive
image updates on their own, for what it's worth -- the bind mount isn't
about that, it's specifically about making backups straightforward.

## 1. Pick a data path and set it explicitly

Don't rely on the `./data` default when deploying through Portainer --
Portainer stacks run from their own working directory (typically something
like `/data/compose/<stack-id>/` on the host), so a relative path lands
inside Portainer's internal directory tree, not somewhere you'd think to
look for backups. Set an absolute path instead, in whichever share you
actually back up:

```
CURB_DATA_DIR=/volume1/docker/curb-selfhosted/data
```

(Synology-style path shown; adjust for your NAS -- QNAP, TrueNAS, etc. all
have their own share layout.)

**Use a local filesystem path, not an SMB/CIFS-mounted share.** Postgres
needs real Unix file locking and permission semantics to run correctly;
network filesystem shares mounted into the Docker host can silently break
this in ways that are hard to diagnose later. If your NAS's Docker data
root is already on a native filesystem (Btrfs, ext4, ZFS), a path under
that is what you want.

## 2. Deploying the stack in Portainer

Add this as a Portainer **Stack**, either pointing at your Git repository
directly (Portainer will pull `docker-compose.yml` from it) or by pasting
the compose file's contents in. Either way, set the environment variables
(`POSTGRES_PASSWORD`, `GRAFANA_ADMIN_PASSWORD`, `CURB_DATA_DIR`, etc.)
through Portainer's own **Environment variables** field on the stack, not
by committing a real `.env` file anywhere -- that's the same reasoning as
not committing `.env` to this repo (see `.gitignore`).

## 3. Permissions

TimescaleDB's official image runs its entrypoint as root initially and
`chown`s `$PGDATA` to the postgres user before dropping privileges, so a
freshly-created empty directory usually just works without any manual
`chown`. Grafana's image is less consistently self-healing about this
across versions -- if it fails to start with a permissions error on first
boot, `chown` the Grafana subdirectory to UID `472` (Grafana's default
container user) from your NAS's shell or file manager permission settings:

```
chown -R 472:472 /volume1/docker/curb-selfhosted/data/grafana
```

## 4. Updating

Portainer's "Update the stack" (or `docker compose pull && docker compose
up -d` if you're doing it by hand) recreates the containers against the
image tags pinned in `docker-compose.yml`, but never touches
`${CURB_DATA_DIR}` -- it's a bind mount to a path outside any container's
writable layer, so your data and Grafana dashboards/config survive exactly
as you'd expect across every update.

## 5. If you hit "Bind mount failed: ... does not exist" on deploy

`timescaledb` and `grafana` build their own images (from `db/Dockerfile` and
`grafana/Dockerfile`) with the schema init script and Grafana provisioning
baked in, specifically so this doesn't happen -- but if you're on an older
checkout, or Portainer's git-based stack deploy doesn't check out every
directory in the repo (some versions only reliably fetch what a `build:`
context needs, not arbitrary relative bind-mount paths), you can hit exactly
this error. Confirm you're on a version of this repo where `docker-compose.yml`
has `build: ./db` and `build: ./grafana` (not `image:`) for those two
services -- if you're not, `git pull` and redeploy the stack fresh (delete
and re-add it in Portainer, not just "Update the stack", so it re-clones).

## 6. Backups

Back up `${CURB_DATA_DIR}` (both the `pgdata` and `grafana` subdirectories
under it) with whatever mechanism your NAS already provides -- a scheduled
snapshot or Hyper Backup job pointed at that folder is all you need.
Modern block-level snapshots (Btrfs, ZFS, Synion's own snapshot engine) are
crash-consistent, meaning a snapshot taken while the stack is running is
equivalent to what Postgres would see after an unclean shutdown -- it
replays its write-ahead log on next start and recovers cleanly, the same
way it would after a real power loss. If you want the simplest possible
guarantee instead of relying on that, `docker compose stop` briefly before
a backup and `docker compose start` after is the fully bulletproof version.
