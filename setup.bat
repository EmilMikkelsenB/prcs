@echo off
rem Windows twin of setup.sh: writes .env, starts the stack, waits for health.
rem Secrets go through PowerShell env vars so cmd never parses them (! % & etc. stay safe).
setlocal
cd /d "%~dp0"

where docker >nul 2>&1 || (echo docker not found on PATH. 1>&2 & exit /b 1)
docker compose version >nul 2>&1 || (echo 'docker compose' not available. 1>&2 & exit /b 1)

set "SKIP_ENV="
if exist .env (
  set "keep=Y"
  set /p "keep=.env already exists - keep it as-is and just start the stack? [Y/n] "
  if /i "%keep%"=="Y" set "SKIP_ENV=1"
  if "%keep%"=="" set "SKIP_ENV=1"
)
if defined SKIP_ENV goto start

set "admin_user=admin"
set /p "admin_user=Admin username [admin]: "
if "%admin_user%"=="" set "admin_user=admin"

:pw
for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "$s=Read-Host 'Admin password' -AsSecureString; [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))"`) do set "admin_password=%%p"
if not defined admin_password (echo Password can't be empty. & goto pw)

set "dash_host=localhost"
set /p "dash_host=Host/IP this dash will be reached at [localhost]: "
if "%dash_host%"=="" set "dash_host=localhost"
echo.
echo GitHub OAuth App - open this, it's pre-filled, just click 'Register application':
powershell -NoProfile -Command "$h=$env:dash_host; $e={[uri]::EscapeDataString($args[0])}; '  https://github.com/settings/applications/new?oauth_application[name]=wellqon-cadence&oauth_application[url]=' + (& $e \"http://${h}:8088\") + '&oauth_application[callback_url]=' + (& $e \"http://${h}:8088/auth/github/callback\")"
echo.

set "oauth_id="
set /p "oauth_id=GitHub OAuth client ID (Enter to skip, fill in .env later): "
set "oauth_secret="
if defined oauth_id for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "$s=Read-Host 'GitHub OAuth client secret' -AsSecureString; [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))"`) do set "oauth_secret=%%p"

powershell -NoProfile -Command "[IO.File]::WriteAllText('.env', \"ADMIN_USER=$env:admin_user`nADMIN_PASSWORD=$env:admin_password`nGITHUB_OAUTH_CLIENT_ID=$env:oauth_id`nGITHUB_OAUTH_CLIENT_SECRET=$env:oauth_secret`n\")"
echo Wrote .env.

:start
echo Starting containers...
docker compose up --build -d || exit /b 1

<nul set /p "=Waiting for the dash to come up"
for /l %%i in (1,1,30) do (
  curl -fsS http://localhost:8088/api/health >nul 2>&1 && goto up
  <nul set /p "=."
  timeout /t 2 /nobreak >nul
)
echo.
echo Still not responding after 60s - check: docker compose logs host 1>&2
exit /b 1

:up
echo  - up.
echo.
echo Open http://localhost:8088 and sign in.
echo One-time: docker compose run runner claude login
