# Wellqon Cadence

Generic, dockerized control panel for Claude Code agent loops: create loops,
chain them into flowpaths, target any GitHub repo you authorize.

Generalizes [rotaria-dash](../rotaria-dash), which hardcodes exactly two
loops against one repo. Design background: see that repo's
`/root/.claude/plans/deep-plotting-hollerith.md`.

## What's here

- `host/` — UI + API container. Login, GitHub OAuth connect flow, loop and
  flowpath CRUD, and the flowpath scheduler (a background polling tick).
- `runner/` — the container with `git`, `gh`, and the `claude` CLI. Clones
  its own copy of a loop's target repo per run and executes it.
- `web/` — React UI (Loops, Flowpaths, GitHub connect, login).
- `tests/` — unit tests for the non-trivial logic: config validation and
  the once/continuous flowpath scheduling decision.

New here? Run `./setup.sh`, or read `ONBOARDING.md` for the manual walkthrough
start to finish. Below is the condensed reference version.

## One-time setup

1. **GitHub OAuth App**: in your GitHub account, Settings → Developer
   settings → OAuth Apps → New OAuth App. Set the callback URL to
   `http://<your-host>:8088/auth/github/callback`. Put the resulting
   client id/secret in a `.env` file next to `docker-compose.yml`:
   ```
   ADMIN_USER=you
   ADMIN_PASSWORD=choose-a-password
   GITHUB_OAUTH_CLIENT_ID=...
   GITHUB_OAUTH_CLIENT_SECRET=...
   ```
   `ADMIN_USER`/`ADMIN_PASSWORD` bootstrap the single dash login account on
   first boot; they're ignored once `data/users.json` exists.

2. **Build and start**:
   ```sh
   docker compose up --build
   ```
   On a normal `docker compose` setup, `runner` gets a fixed IP on the
   compose network: `172.28.0.10:8089`. `host` talks to it there by default
   (`RUNNER_URL`). To point at a runner running somewhere else (bare metal,
   another host, a different compose stack), set `RUNNER_URL=http://<ip>:<port>`
   in `.env` — any reachable address works, not just the default static IP.

3. **Claude login** (one-time, persists into the `claude_creds` volume):
   ```sh
   docker compose run runner claude login
   ```

4. Open `http://<your-host>:8088`, sign in, connect GitHub, create a loop,
   and optionally chain loops into a flowpath.

## Known limits (read before relying on this)

- **Session logout is client-side only.** Cookies are signed, not tracked
  server-side, so logout clears the browser cookie but a copy of a token
  taken before logout stays valid until it expires (30 days).
- **GitHub token at rest** uses a hand-rolled HMAC-SHA256 keystream cipher
  (see `host/github_oauth.py`), not a peer-reviewed AEAD. Acceptable for a
  self-hosted single-user token behind the session secret; revisit before
  storing anything more sensitive.
- **No multi-user, roles, or database** — explicitly out of scope for v1.
- This was built and unit-tested without Docker or a real GitHub OAuth App
  or `claude` login available in the dev environment. Verified directly:
  the HTTP API (auth, loop/flowpath CRUD, static serving), the host↔runner
  `/runs` lifecycle (start → poll → failure handling) against a fake repo,
  and the flowpath scheduler's trigger decisions (unit tests). **Not yet
  verified**: the actual `docker build`/`docker compose up` (no `docker`
  binary in the dev sandbox), the real GitHub OAuth token exchange, and an
  actual `claude -p` run against a real repo. Check these first when you
  pick this up.

## Try it without Docker (for local hacking)

```sh
# terminal 1
cd runner && RUNNER_PORT=8098 python3 runner_app.py
# terminal 2
cd host && DASH_DATA=/tmp/alh-data ADMIN_USER=admin ADMIN_PASSWORD=pw \
  HOST_PORT=8099 RUNNER_URL=http://127.0.0.1:8098 python3 app.py
# terminal 3
cd web && npm install && npm run build   # then point HOST at web/dist, or `npm run dev` and proxy
```

## Tests

```sh
python3 -m pytest tests/
```
