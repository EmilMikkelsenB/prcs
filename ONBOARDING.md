# Onboarding: first run, start to finish

Fastest path: run `./setup.sh` and follow its prompts — it does steps 1-3
below for you (including printing a pre-filled OAuth app link) and starts
the stack. The rest of this doc is the manual version, and still useful
for step 4 onward.

Follow in order. Each step says what you'll see and what to do.

## 1. Register a GitHub OAuth App

GitHub → Settings → Developer settings → OAuth Apps → New OAuth App.

- Homepage URL: `http://<your-host>:8088`
- Authorization callback URL: `http://<your-host>:8088/auth/github/callback`

Copy the client ID and generate a client secret.

Shortcut: GitHub's form accepts prefill via query string. Replace
`<your-host>` and open this link — the name/URL/callback fields are
already filled in, just click "Register application":
```
https://github.com/settings/applications/new?oauth_application[name]=agent-loop-dash&oauth_application[url]=http://<your-host>:8088&oauth_application[callback_url]=http://<your-host>:8088/auth/github/callback
```

## 2. Write `.env`

Next to `docker-compose.yml`:

```
ADMIN_USER=you
ADMIN_PASSWORD=choose-a-password
GITHUB_OAUTH_CLIENT_ID=<from step 1>
GITHUB_OAUTH_CLIENT_SECRET=<from step 1>
```

`ADMIN_USER`/`ADMIN_PASSWORD` only take effect on first boot (they create
the single login account); edit `data/users.json` later to change the
password.

## 3. Start the containers

```sh
docker compose up --build
```

`runner` comes up at the static IP `172.28.0.10:8089` on the compose
network by default. Running the runner somewhere else (another box, bare
metal)? You'll set its address in step 6, not here — nothing in this step
needs editing for that case.

## 4. One-time `claude login`

```sh
docker compose run runner claude login
```

Follow the device-code prompt. This persists into the `claude_creds`
volume, so you don't repeat it on restarts — only if that volume is removed.

## 5. Open the dash and sign in

`http://<your-host>:8088` → sign in with `ADMIN_USER`/`ADMIN_PASSWORD`.

## 6. Runner address

On a standard setup this is skipped automatically — the host checks the
default compose IP (`172.28.0.10:8089`) and, if it answers, just uses it.
You'll only see a **"Where is the runner?"** prompt if that check fails
(runner not up yet, or it lives elsewhere — another machine, a different
compose stack). Type its real `http://<ip>:<port>` and save. This is
stored in `data/config.json` and can be changed later the same way.

## 7. Connect GitHub

**GitHub** tab → **Connect GitHub** → authorize on GitHub's site → you're
redirected back with a connected status. This is what lets you pick a
target repo by name and lets the runner push/open PRs.

## 8. Create a loop

**Loops** tab → new loop:
- Role: `producer` (writes backlog ideas) or `consumer` (implements +
  opens a PR).
- Target repo: pick from your authorized repos.
- Focus: a preset or custom prompt text.
- Tuning: leave defaults unless you know you want different sleep/retry
  timing.

## 9. (Optional) Chain loops into a flowpath

**Flowpaths** tab → name it, add links in order, pick `once` (runs
exactly once per new upstream output, then hands off) or `continuous`
(keeps its own schedule, gated on new upstream output) per link.

## You're done

The scheduler ticks in the background every 10s. Watch a loop/flowpath's
run status in the UI; stop a stuck run from there too.

## If something's wrong

See `README.md`'s **Known limits** section first — it lists what's
verified and what isn't (real Docker build, real OAuth exchange, real
`claude` run) as of this writing.
