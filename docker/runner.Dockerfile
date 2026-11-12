FROM python:3.12-slim

# git + gh (official apt repo) + node (for the claude CLI).
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates gnupg git nodejs npm \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# Pin this once a tested version is chosen (docs/PRODUCT.md flags unpinned
# Claude Code as a risk: flags/stream format change between versions).
ARG CLAUDE_CODE_VERSION=latest
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}

WORKDIR /app
COPY runner/ /app/runner/
ENV RUNNER_BIND=0.0.0.0 RUNNER_PORT=8089
EXPOSE 8089
CMD ["python3", "-I", "runner/runner_app.py"]
