"""Per-run workspace: the runner clones its own copy of the target repo
(no bind mount), caching it under /workspace/<project-id> and pulling on
later runs instead of re-cloning every time."""
import os
import subprocess

WORKSPACE_ROOT = os.environ.get("WORKSPACE_ROOT", "/workspace")


def _authed_url(target_repo, github_token):
    return f"https://x-access-token:{github_token}@github.com/{target_repo}.git"


def ensure_workspace(target_repo, github_token):
    project_id = target_repo.replace("/", "__")
    path = os.path.join(WORKSPACE_ROOT, project_id)
    url = _authed_url(target_repo, github_token)
    if os.path.isdir(os.path.join(path, ".git")):
        subprocess.run(["git", "remote", "set-url", "origin", url], cwd=path, check=True, capture_output=True)
        subprocess.run(["git", "fetch", "-q", "origin"], cwd=path, check=True, capture_output=True)
        default = subprocess.run(["git", "rev-parse", "--abbrev-ref", "origin/HEAD"],
                                  cwd=path, capture_output=True, text=True).stdout.strip().removeprefix("origin/") or "main"
        subprocess.run(["git", "checkout", "-qf", default], cwd=path, check=True, capture_output=True)
        subprocess.run(["git", "reset", "-q", "--hard", f"origin/{default}"], cwd=path, check=True, capture_output=True)
        subprocess.run(["git", "clean", "-fdq"], cwd=path, check=True, capture_output=True)
    else:
        os.makedirs(WORKSPACE_ROOT, exist_ok=True)
        subprocess.run(["git", "clone", "-q", url, path], check=True, capture_output=True)
    return path
