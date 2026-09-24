# Release v1.0.61 (build 106) — backend schema v27 + audit hardening

Scope: PR "Full audit: child-safety guard order, security fixes, UX-0/1/2 + roadmaps".
Everything below is copy-paste ready; run it on the VPS from `/root/tutor-guardian`
unless stated otherwise. Always pass `-f docker-compose.production.yml` — the bare
`docker compose` reads the dev file and once exposed port 8000 past Cloudflare.

## 0. What changes in production behaviour

| Change | Visible effect | Env knob |
|---|---|---|
| Emergency check runs before the fiqh guard | Suicidal/emergency disclosures always get the emergency escalation | — |
| Fiqh guard precision | Newborn / backbiting / eyesight / parental-control questions answered normally | — |
| Session ownership on `/api/assistant/*` | Foreign `session_id` → 404 (the app recovers by opening a session) | — |
| Schema v27 (`child_challenges`) | Changing a child's challenge ≥3 times stops returning 500 | — |
| `/api/sync/*` reachable + authenticated | Encrypted backups work (no client uses them yet) | — |
| ClientIPMiddleware (outermost) | Rate limits key on the real client IP (Cloudflare → nginx) | `TRUSTED_PROXY_IPS` (default: private + Cloudflare ranges) |
| AI scope validates tokens; `/api/insights` in the AI quota | Random `Bearer` values no longer reset quotas | `AI_DAILY_LIMIT` |
| Session minting budget | `POST /api/chat/sessions` ≤ 30/min per IP | `RATE_LIMIT_SESSION_PER_MINUTE` |
| Session-mint proof (staged) | Logged only until enforced | `SESSION_MINT_ENFORCE` (leave **unset** for now, see §5) |
| SSE streams cancel on disconnect, own pool, deadline | Abandoned answers release their worker | `LLM_STREAM_WORKERS` (8), `LLM_STREAM_DEADLINE_S` (300) |

## 1. Pre-deploy (backend)

```bash
cd /root/tutor-guardian
# Read-only report — expect schema_version=26, legacy key present=True,
# "children with >1 active challenge" = 0, integrity_check=ok.
ops/scripts/migrate_schema_v27.sh preflight

# Verified backup (sqlite online-backup API — same as `sqlite3 DB ".backup FILE"`;
# the host and the slim image have no sqlite3 CLI). Prints the backup path.
BACKUP=$(ops/scripts/migrate_schema_v27.sh backup | tail -1); echo "$BACKUP"

# Record the image to roll back to.
PREV_IMAGE=$(docker inspect tg_backend --format '{{.Image}}'); echo "$PREV_IMAGE"
```

If you have the sqlite3 CLI somewhere with access to the volume, the equivalent
manual backup is:

```bash
sqlite3 /var/lib/docker/volumes/tutor-guardian_tg_sessions/_data/conversations.db \
  ".backup '/root/tg-backups/pre-v27/conversations.manual.db'"
```

## 2. Deploy (backend)

Normal path: merge to `main` — `deploy.yml` builds a candidate image, runs pytest +
KB integrity inside it, tags it `tutor-guardian-backend:latest`, recreates the
container, health-checks `/health` and `/privacy-policy`, and rolls back on failure.

Manual path (same steps, e.g. `workflow_dispatch` unavailable):

```bash
cd /root/tutor-guardian
git fetch origin main && git reset --hard origin/main
docker buildx build -f backend/Dockerfile -t tutor-guardian-backend:candidate-$(git rev-parse --short HEAD) .
docker run --rm -e SKIP_API_SMOKE=1 -e PYTHONPATH=/app/backend \
  tutor-guardian-backend:candidate-$(git rev-parse --short HEAD) pytest -q
docker tag tutor-guardian-backend:candidate-$(git rev-parse --short HEAD) tutor-guardian-backend:latest

# The reload/restart itself:
docker compose -f docker-compose.production.yml up -d --no-build --remove-orphans backend

# Wait for healthy (≤ 90 s: ONNX + Chroma warm-up), then smoke:
until [ "$(docker inspect -f '{{.State.Health.Status}}' tg_backend)" = healthy ]; do sleep 5; done
curl -fsS https://tg-api.alsaba.cloud/health
curl -fsS -o /dev/null -w '%{http_code} %{size_download}\n' https://tg-api.alsaba.cloud/privacy-policy
```

A config-only change (env var in `.env`) needs no rebuild — just
`docker compose -f docker-compose.production.yml up -d --no-build --force-recreate backend`.

## 3. Post-deploy verification

```bash
# The app migrated itself on startup; this asserts the end state.
ops/scripts/migrate_schema_v27.sh verify        # → "VERIFY OK — v27 in place"
# (If it reports schema_version < 27, run `ops/scripts/migrate_schema_v27.sh apply`.)

# Rate-limit identity: keys should now be many client IPs, not one nginx IP.
docker exec tg_redis redis-cli --scan --pattern 'rl:api:ip:*' | head
docker logs --since 10m tg_backend 2>&1 | grep -c ' 429 ' || true

# Guard order (from a trusted shell with a token): an emergency disclosure
# mentioning divorce must return escalation_target=emergency_services.
```

## 4. Rollback

```bash
# Code: deploy.yml's _rollback does this automatically on a failed health check.
docker tag "$PREV_IMAGE" tutor-guardian-backend:latest
docker compose -f docker-compose.production.yml up -d --no-build --remove-orphans backend

# Data (only if v27 itself misbehaves — it is additive and idempotent):
ops/scripts/migrate_schema_v27.sh rollback "$BACKUP"   # stops, restores, restarts
```

## 5. Staged switches (do NOT flip on this release)

- `SESSION_MINT_ENFORCE=true` — refuse minting for a known device without proof.
  Build 106 is the first build that sends proof. Flip only after
  `MINIMUM_BUILD_NUMBER` ≥ 106 (forced-update floor) and the census in
  `push_tokens.build_number` shows the old builds are gone. Then
  `up -d --no-build --force-recreate backend`.
- `STORY_AUTH_ENFORCE=true` — unchanged guidance (OPS_RUNBOOK).
- `TRUSTED_PROXY_IPS` — only if Cloudflare publishes new ranges or nginx moves off
  the private Docker network.

## 6. Android release (v1.0.61+106)

```bash
cd mobile
flutter pub get && flutter analyze && flutter test
flutter build appbundle --release
# → build/app/outputs/bundle/release/app-release.aab
```

Signing: `android/app/build.gradle.kts` uses the upload keystore only when
`android/app/key.properties` exists; otherwise it silently signs with the
**debug** key, which Play Console rejects. Build the upload artifact on the
machine that holds `key.properties` + `almorabbi-upload.jks`, then verify:

```bash
jarsigner -verify -verbose -certs build/app/outputs/bundle/release/app-release.aab | grep -E "CN=|jar verified"
# Must NOT show "CN=Android Debug".
```

Reference build from the audit environment (no upload keystore there):
`app-release.aab` — 94.4 MB, versionCode **106**, versionName **1.0.61**, ABIs
arm64-v8a / armeabi-v7a / x86_64, zip CRCs OK, `jar verified` — signed with
**CN=Android Debug**, so it is a build-health check only, not an upload artifact.

Play Console → Production → Create release → upload `app-release.aab`
(versionCode 106) → release notes (ar/en) from `features/whats_new/data`.

## 7. Checklist

- [ ] §1 preflight + backup done, `$BACKUP` and `$PREV_IMAGE` noted
- [ ] PR merged → deploy.yml green (or §2 manual path)
- [ ] §3 `verify` OK, health + privacy 200
- [ ] Redis keys show real client IPs; no 429 spike in logs
- [ ] AAB signed with the upload key, uploaded to Play (internal → production)
- [ ] After adoption: raise `MINIMUM_BUILD_NUMBER`, then consider `SESSION_MINT_ENFORCE`
- [ ] C3 settings: *Actions → Fork pull request workflows → Require approval for all outside collaborators*
