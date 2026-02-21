---
description: Deploy containers locally using Docker Compose
---

## Deploy a single service (with cache — fast)
```bash
docker compose up --build -d <service>
# e.g. docker compose up --build -d web
```

## Deploy a single service (no cache — use when changes aren't picked up)
```bash
docker compose build --no-cache <service> && docker compose up -d --no-deps <service>
# e.g. docker compose build --no-cache web && docker compose up -d --no-deps web
```

## Deploy all services
```bash
docker compose up --build -d
```

## Restart Caddy only (config changes)
```bash
docker restart mie-caddy
```

## Check container status
```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

## View logs for a service
```bash
docker logs mie-api --tail 50 -f
docker logs mie-caddy --tail 20
```

## Notes
- Services: `api`, `web`, `caddy`, `scheduler`, `theta_terminal`
- Always use `http://localhost` (not https) for local access
- If browser shows SSL error, clear HSTS: `chrome://net-internals/#hsts` → delete `localhost` and `127.0.0.1`
- If changes aren't visible after deploy, use `--no-cache` build (stale Docker layer cache)
