# InvoiceNinja Docker volumes

`docker-compose.yaml` declares two named volumes that are mounted into the
`app` container and (read-only) into `nginx`:

| Volume       | Mount point inside container   | Purpose                                                                     |
| ------------ | ------------------------------ | --------------------------------------------------------------------------- |
| `app_public` | `/var/www/html/public`         | Web root. Holds uploaded company logos, generated PDFs, CSS/JS bundles that nginx serves directly. |
| `app_storage`| `/var/www/html/storage`        | Laravel app storage: logs, framework cache, sessions, queued job payloads, user uploads. |

The `mysql` and `redis` containers also use named volumes (`mysql_data`,
`redis_data`) so databases and cache state survive `docker compose down`.

## You don't create the directories

These are **Docker named volumes**, not host bind mounts. On first
`docker compose up -d` Docker creates them under
`/var/lib/docker/volumes/<project>_app_public/_data` (path varies by driver)
and the containers see them as ordinary directories.

Inspect what's actually stored:

```bash
docker volume ls                                  # list all named volumes
docker volume inspect <project>_app_public        # see the mountpoint on the host
docker compose exec app ls -la /var/www/html/public
```

## Why two separate volumes

* nginx mounts them `:ro` so the web server can only read what the app wrote.
* Backups are independent: a `tar` of `app_storage` gets you logs and cache
  separately from `app_public` (logos / generated PDFs).

## Switching to host bind mounts (optional)

If you'd rather keep the data on the host filesystem — easier to back up with
`rsync`, browse with normal tools, or mount into other services — replace the
top-level `volumes:` entries and the matching service mounts:

```yaml
services:
  app:
    volumes:
      - ./data/app_public:/var/www/html/public
      - ./data/app_storage:/var/www/html/storage
  nginx:
    volumes:
      - ./data/app_public:/var/www/html/public:ro
      - ./data/app_storage:/var/www/html/storage:ro

volumes:
  mysql_data: {}
  redis_data: {}
  # app_public and app_storage removed
```

Then `mkdir -p data/app_public data/app_storage` before bringing the stack up.
For everyday use the named volumes are fine and recommended.

## Backing up

```bash
# Tar a named volume to a host file
docker run --rm \
  -v <project>_app_storage:/from:ro \
  -v "$PWD":/to \
  alpine tar -czf /to/app_storage-$(date +%F).tgz -C /from .
```

Do the same for `app_public`, `mysql_data` (`mysqldump` is usually simpler),
and `redis_data` (stop the container, copy `/data/dump.rdb`).