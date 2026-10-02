# Synced from eval/verifier/shared/Dockerfile by eval/scripts/sync_tests.py. Do not edit here.
FROM node:22-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl ca-certificates python3 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
ENV UV_TOOL_BIN_DIR=/usr/local/bin
RUN uv tool install harbor-rewardkit==0.2.1
# Preinstalled agent CLIs: Harbor skips its per-trial install when the binary
# already matches the version pinned in eval/agents/*.yaml, and the RewardKit
# judge reuses `claude` from PATH. Keep these versions in step with those files.
RUN npm install -g @anthropic-ai/claude-code@2.1.282 @openai/codex@0.156.1 \
    && npm cache clean --force

COPY workspace/ /app
WORKDIR /app
# Commit the scaffold so the verifier can read the agent's changes with git.
# The SHA lives outside /app so the diff base survives agent commits, and
# node_modules stays out of every diff even without an agent .gitignore.
RUN git init -q \
    && git add -A \
    && git -c user.name=eval -c user.email=eval@example.com commit -qm scaffold \
    && echo "node_modules/" >> .git/info/exclude \
    && mkdir -p /opt/eval \
    && git rev-parse HEAD > /opt/eval/scaffold.sha
