# pgscratch

Disposable Postgres in a container, for quick throwaway DB work — load a dump, poke it, throw it away —
without touching a local (e.g. Homebrew) Postgres.

It targets **Apple `container`** (per-container microVM, no Docker Desktop) or **Docker**, whichever is on
PATH. The connection is published on `127.0.0.1:<port>` (default `5433`, to dodge a local Postgres on
`5432`), so existing `psql` / oerplib tooling connects unchanged.

## Why

A lot of DB work needs a clean, isolated, *temporary* Postgres: validating a SQL fix or an oerplib script
against a fresh slice, then discarding it. `pgscratch` spins one up, optionally restores a dump, and tears
it down — the throwaway lifecycle in one command, isolated from your real local databases.

## Requirements

- `apple/container` (macOS 26 + Apple Silicon) **or** Docker on PATH.
- A reachable Postgres image (`postgres:17` by default — first run pulls it).
- Dumps are restored through the **container's own** `psql`/`pg_restore`, so no host Postgres client is
  needed and the client version always matches the server.

## Usage

```bash
# Start a disposable Postgres (optionally restoring a dump), print the connection line
pgscratch up
pgscratch up --dump pets_clean.sql
pgscratch up --dump pets_test.dump        # custom-format (pg_dump -Fc) → pg_restore

# Open psql against it (extra args after --)
pgscratch psql
pgscratch psql -- -c "select count(*) from res_partner;"

# Show state + connection string
pgscratch status

# Stop and remove it
pgscratch down

# Ephemeral: run a command with PG* set, then tear down (great for script validation / CI)
pgscratch run --dump pets_clean.sql -- ./v27/bin/python src/scripts/ERP-XXXX_check.py
pgscratch run -- psql -c "select version();"
```

`run` exports `PGHOST`/`PGPORT`/`PGUSER`/`PGPASSWORD`/`PGDATABASE` for the child command and always tears
the container down afterwards (even on failure).

## Dump formats

| Extension | Restored with |
|---|---|
| `.sql` | `psql` |
| `.sql.gz` | `psql` (decompressed on the fly) |
| `.dump`, `.backup`, `.pgdump` | `pg_restore --no-owner --no-privileges` |

Produce a custom-format dump with `pg_dump -Fc <db> > db.dump`.

## Configuration (env vars)

| Var | Default | Purpose |
|---|---|---|
| `PGSCRATCH_RUNTIME` | auto (`container`, else `docker`) | force the container runtime |
| `PGSCRATCH_IMAGE` | `postgres:17` | Postgres image |
| `PGSCRATCH_PORT` | `5433` | host port to publish |
| `PGSCRATCH_NAME` | `pgscratch` | container name |
| `PGSCRATCH_USER` / `PGSCRATCH_PASSWORD` / `PGSCRATCH_DB` | `openerp_pets` / `scratch` / `scratch` | credentials + db |
| `PGSCRATCH_READY_TIMEOUT` | `60` | seconds to wait for Postgres to accept connections |

## Notes & caveats

- **Disposable by design** — started with `--rm` and no volume; stopping it discards all data. (For a
  persistent dev DB, use the project's `docker compose` stack instead.)
- **`run` and `up` share the default port.** `run` uses a separate container name (`pgscratch-run-<pid>`),
  so if you already have an `up` instance on `5433`, give `run` a different `--port`.
- **Apple `container` needs its service running.** Start it once per boot with `container system start`.
  An `XPC connection error: Connection invalid` means the service isn't up.
- **Apple `container` is new (~1.0).** If it misbehaves, set `PGSCRATCH_RUNTIME=docker` to fall back.

## Readiness

`up`/`run` wait in two phases: first that Postgres is listening **inside** the container, then that it is
reachable on the **host** published port. The host check matters for Apple `container`, which can lag on
port forwarding during a container's first boot (in-container readiness alone would report ready too
early). It prefers a real `pg_isready` probe on the host when available, falling back to a TCP connect.

## Validation

Pure functions have pytest coverage (`tests/test_pgscratch.py`). Validated end-to-end on **both runtimes**:

- **Docker:** `up`/`down`/`status`/`psql`, `.sql` restore, host-side query on the published port, `run`
  (ephemeral + `PG*` env + teardown).
- **Apple `container`:** full **cold start** (image pull → microVM boot → host reachable on the published
  port — the first-boot port-forward race is handled) and a **`pg_restore`** custom-format (`pg_dump -Fc`)
  restore round-trip. Needs `container system start` first.
