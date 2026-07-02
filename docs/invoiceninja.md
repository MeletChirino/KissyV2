# InvoiceNinja

Self-hosted invoicing, expenses, and time-tracking using the official
[`invoiceninja/invoiceninja-debian`](https://hub.docker.com/r/invoiceninja/invoiceninja-debian)
image, fronted by nginx, with MySQL 8 and Redis for storage and queue.

`docker-compose.yaml` runs four services:

| Service | Image                        | Purpose                                |
| ------- | ---------------------------- | -------------------------------------- |
| `app`   | `invoiceninja/invoiceninja-debian:latest` | PHP-FPM + queue workers + scheduler    |
| `nginx` | `nginx:alpine`               | Reverse proxy, serves `public/`        |
| `mysql` | `mysql:8`                    | Database                               |
| `redis` | `redis:alpine`               | Queue / cache                          |

nginx uses `docker-compose.yaml:24` to bind-mount `./nginx` into
`/etc/nginx/conf.d`, which is where `laravel.conf` (the vhost) and
`invoiceninja.conf` (gzip, body size, server tokens) live.

## Quick start

```bash
cp .env.example .env             # already done in this repo, but for a fresh clone
docker compose pull              # fetch the latest image
docker compose up -d             # start app, nginx, mysql, redis
open http://localhost/           # InvoiceNinja login page
```

Default admin (set in `.env`, change immediately after first login):

```
email:    admin@example.com
password: changeme!
```

Once logged in, remove `IN_USER_EMAIL` and `IN_PASSWORD` from `.env` and
recreate the app container so they don't seed a new account on the next boot:

```bash
docker compose up -d --force-recreate app
```

## Environment variables

The app container reads the **same `.env`** as the Telegram bot (it uses
`env_file: ./.env`). Variables are grouped into bot-only and InvoiceNinja-only
sections by `# ---` comments. The full set the InvoiceNinja image expects:

| Variable          | Required | Purpose                                                           |
| ----------------- | -------- | ----------------------------------------------------------------- |
| `APP_URL`         | yes      | Public URL the app is reached at. Must match how you hit nginx.   |
| `APP_KEY`         | yes      | 32-char base64 Laravel key. See "Generating APP_KEY" below.       |
| `APP_ENV`         | yes      | `production` or `local`. The image's `init.sh` hard-codes behaviour on this. |
| `APP_DEBUG`       | no       | `true` / `false`. `false` in production.                          |
| `REQUIRE_HTTPS`   | no       | Set `true` once a TLS-terminating proxy fronts nginx.             |
| `DB_HOST`         | yes      | Service name of the MySQL container: `mysql`.                     |
| `DB_PORT`         | no       | `3306` by default.                                                |
| `DB_DATABASE`     | yes      | Schema name; matched by `MYSQL_DATABASE` in the mysql container.  |
| `DB_USERNAME`     | yes      | App DB user.                                                      |
| `DB_PASSWORD`     | yes      | App DB password.                                                  |
| `DB_ROOT_PASSWORD`| yes      | Only used by the mysql container to bootstrap.                    |
| `MYSQL_USER`      | yes      | Mirror of `DB_USERNAME` for the mysql healthcheck.                |
| `MYSQL_PASSWORD`  | yes      | Mirror of `DB_PASSWORD` for the mysql healthcheck.                |
| `IN_USER_EMAIL`   | first boot only | Seeds the initial admin account. Remove after first login. |
| `IN_PASSWORD`     | first boot only | Seeds the initial admin password. Remove after first login. |

The `MYSQL_*` variables look like duplicates of `DB_*` but they're consumed
by a different code path — the `mysqladmin ping` healthcheck inside the
mysql container. If they're unset, `docker compose up` prints harmless
warnings; setting them makes the output clean.

## Generating `APP_KEY`

The official image will auto-generate a key on first boot, but it gets baked
into the cached config and you'll get a 500 if you later rotate it without
clearing the cache. Best to set it explicitly before first boot:

```bash
docker compose run --rm app php artisan key:generate --show
# prints: base64:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx=
```

Paste that value into `.env` as `APP_KEY=base64:...`. Rotate later with:

```bash
docker compose run --rm app php artisan key:generate --force --show
docker compose exec app php artisan config:clear
docker compose restart app
```

## First-boot failures and fixes

These all came up while bringing the stack up the first time:

| Symptom (log line)                                        | Cause                                              | Fix                              |
| ---------------------------------------------------------- | -------------------------------------------------- | -------------------------------- |
| `APP_ENV: parameter not set`                              | `.env` missing `APP_ENV`, init uses `set -u`       | Add `APP_ENV=production`         |
| `SQLSTATE[HY000] [2002] Connection refused` at `127.0.0.1:3306` | Laravel defaulting to localhost; needs `DB_HOST`   | Add `DB_HOST=mysql`              |
| `IN_USER_EMAIL: parameter not set` and `exit 1`           | `init.sh` requires both vars on first boot         | Set `IN_USER_EMAIL` + `IN_PASSWORD` |
| `Welcome to nginx!` instead of InvoiceNinja               | `nginx/` vhost not mounted into container          | Ensure `docker-compose.yaml` mounts `./nginx:/etc/nginx/conf.d:ro` |
| `500 Server Error` after fresh boot                        | `APP_KEY` empty                                    | Generate and set `APP_KEY`       |
| `502 Bad Gateway` right after `--force-recreate`          | Cached config still references old `APP_KEY`       | `docker compose exec app php artisan config:clear && docker compose restart app` |

## Updating

```bash
docker compose pull
docker compose up -d
```

Back up the database and the `app_public` / `app_storage` volumes first. See
[`invoiceninja-volumes.md`](invoiceninja-volumes.md) for backup commands.

## Going behind a reverse proxy

For TLS, put a proxy (nginx, Caddy, Traefik) in front of the exposed port 80.
Then set:

```
APP_URL=https://in.example.com/
REQUIRE_HTTPS=true
APP_DEBUG=false
```

## Resetting everything

Destructive — wipes the database and any uploaded PDFs / logos:

```bash
docker compose down -v              # -v removes named volumes
docker compose up -d
```