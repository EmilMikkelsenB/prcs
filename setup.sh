#!/usr/bin/env bash
# One-command bootstrap: writes .env, starts the stack, waits for it to be
# healthy. Doesn't replace ONBOARDING.md — it just automates steps 2-3 there.
set -euo pipefail
cd "$(dirname "$0")"

urlencode() {
  local s="$1" out="" c i
  for ((i = 0; i < ${#s}; i++)); do
    c="${s:$i:1}"
    case "$c" in
      [a-zA-Z0-9.~_-]) out+="$c" ;;
      *) printf -v c '%%%02X' "'$c"; out+="$c" ;;
    esac
  done
  echo "$out"
}

command -v docker >/dev/null || { echo "docker not found on PATH." >&2; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "'docker compose' not available." >&2; exit 1; }

if [[ -f .env ]]; then
  read -rp ".env already exists — keep it as-is and just start the stack? [Y/n] " keep
  if [[ "${keep:-Y}" =~ ^[Yy]?$ ]]; then
    SKIP_ENV=1
  fi
fi

if [[ -z "${SKIP_ENV:-}" ]]; then
  read -rp "Admin username [admin]: " admin_user
  admin_user="${admin_user:-admin}"
  read -rsp "Admin password: " admin_password; echo
  while [[ -z "$admin_password" ]]; do
    read -rsp "Password can't be empty. Admin password: " admin_password; echo
  done

  read -rp "Host/IP this dash will be reached at [localhost]: " dash_host
  dash_host="${dash_host:-localhost}"
  callback="http://${dash_host}:8088/auth/github/callback"
  echo
  echo "GitHub OAuth App — open this, it's pre-filled, just click 'Register application':"
  echo "  https://github.com/settings/applications/new?oauth_application[name]=$(urlencode "agent-loop-dash")&oauth_application[url]=$(urlencode "http://${dash_host}:8088")&oauth_application[callback_url]=$(urlencode "$callback")"
  echo
  read -rp "GitHub OAuth client ID (Enter to skip, fill in .env later): " oauth_id
  oauth_secret=""
  if [[ -n "$oauth_id" ]]; then
    read -rsp "GitHub OAuth client secret: " oauth_secret; echo
  fi

  cat > .env <<EOF
ADMIN_USER=${admin_user}
ADMIN_PASSWORD=${admin_password}
GITHUB_OAUTH_CLIENT_ID=${oauth_id}
GITHUB_OAUTH_CLIENT_SECRET=${oauth_secret}
EOF
  echo "Wrote .env."
fi

echo "Starting containers..."
docker compose up --build -d

echo -n "Waiting for the dash to come up"
for _ in $(seq 1 30); do
  if curl -fsS http://localhost:8088/api/health >/dev/null 2>&1; then
    echo " — up."
    echo
    echo "Open http://localhost:8088 and sign in."
    echo "One-time: docker compose run runner claude login"
    exit 0
  fi
  echo -n "."
  sleep 2
done
echo
echo "Still not responding after 60s — check: docker compose logs host" >&2
exit 1
