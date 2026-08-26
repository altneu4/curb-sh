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

**Create the directory before your first deploy.** Docker Compose
deliberately refuses to bind-mount a host path that doesn't already exist,
rather than silently creating an empty one -- for a database data
directory, silently creating an empty folder on a typo'd path would be
worse than failing loudly, since it'd look like a successful deploy while
actually starting from a blank database. Run this once, over SSH on the
NAS, with the exact same path you're about to put in `CURB_DATA_DIR`:

```bash
./scripts/init-data-dir.sh /volume1/docker/curb-selfhosted/data
```

(Or `mkdir -p /volume1/docker/curb-selfhosted/data/{pgdata,grafana}` by
hand -- the script just does that, plus double-checks the path you're
about to use.) Skip this and you'll hit `Bind mount failed: ... does not
exists` on deploy.

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
freshly-created empty directory just works without any manual `chown`.

Grafana's image doesn't do this -- it runs as UID `472` from the start, so
by default a directory created by `mkdir` fails Grafana's startup with
`mkdir: can't create directory '/var/lib/grafana/plugins': Permission
denied`, repeating on every restart. `chown -R 472:472` on the Grafana
subdirectory fixes this on a plain Linux host -- but on Synology DSM
specifically (and possibly other NAS platforms with their own ACL layer on
top of Unix permissions), `chown` alone may not be enough: DSM's ACL system
can silently override standard permission bits for a UID that doesn't
correspond to any real Synology user account, denying access even when
`ls -l` shows the directory as world-writable. Editing that ACL via
`synoacltool` or File Station is possible but fiddly and DSM-version-
dependent.

Because of that, `docker-compose.yml` runs the `grafana` service as root
(`user: "0:0"`) rather than relying on host-side ownership/ACLs at all --
the same trust boundary TimescaleDB's image already crosses briefly during
its own startup. `scripts/init-data-dir.sh` doesn't need to `chown`
anything for this reason; both services now manage their own data
directory permissions.

If you'd rather keep Grafana running as its non-root default user (for a
tighter security posture) than take this shortcut, remove the `user: "0:0"`
line from the `grafana` service and either `chown -R 472:472` the directory
(plain Linux hosts) or add an explicit ACL entry for it (Synology):

```bash
# plain Linux / most NAS platforms
chown -R 472:472 /volume1/docker/curb-selfhosted/data/grafana

# Synology DSM, if chown alone doesn't stick because of ACL enforcement
synoacltool -add /volume1/docker/curb-selfhosted/data/grafana \
  "everyone:allow:rwxpdDaARWc--:fd--"
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

## 6. Circuit display configuration (the config-portal service)

If a CT clamp is wired backwards on a circuit, it reports negative watts for
real positive draw, permanently. The `config-portal` service is a small web
UI (default port 8082, e.g. `http://<your-nas>:8082`) for flipping a
per-circuit "invert display" flag that both dashboards read from. New
circuits show up there automatically the first time they report a sample --
nothing to configure by hand for a circuit that isn't inverted.

This depends on a new database table/trigger/role
(`db/init/002_circuit_config.sh`) and a new `PORTAL_DB_PASSWORD` value in
`.env`. Two things to do once when you first pull this update, neither of
which happens automatically on an existing deployment:

1. **Add `PORTAL_DB_PASSWORD` to your `.env`** (see `.env.example`) --
   `timescaledb` and `config-portal` both refuse to start without it.

2. **Run the migration once by hand.** `002_circuit_config.sh` only runs
   automatically the way `001_schema.sql` did on a *brand-new* database --
   Postgres only executes `/docker-entrypoint-initdb.d` scripts against an
   empty data directory, and yours already has data. After redeploying the
   stack (so the new `circuit_portal` role's password matches what you put
   in `.env`), run this once, substituting your own `POSTGRES_DB`/
   `POSTGRES_USER` if you changed them from the defaults and the same value
   you set for `PORTAL_DB_PASSWORD`:

   ```
   docker exec -i curb-timescaledb env PORTAL_DB_PASSWORD='<your PORTAL_DB_PASSWORD>' \
     sh -c 'POSTGRES_USER=curb POSTGRES_DB=curb PORTAL_DB_PASSWORD="$PORTAL_DB_PASSWORD" /docker-entrypoint-initdb.d/002_circuit_config.sh'
   ```

   This is safe to run more than once -- it only ever adds circuits that
   don't already have a config row, and only ever resets the
   `circuit_portal` role's password to match `.env`, never any dashboard
   settings.

If you'd already set the old `invert_circuits` textbox variable on either
dashboard, that variable no longer exists -- re-set the same circuit(s) as
inverted in the config portal instead; it's the one place this lives now.

## 7. Backups

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
