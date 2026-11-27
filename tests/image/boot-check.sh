#!/usr/bin/env bash
# The image's boot gate, run inside the image this PR builds (the boot-gate check
# in pyproject.toml). It was `boot-command` in [tool.sdlc.image], which sdlc does
# not enforce (crunchtools/sdlc#118). Nothing here needs /dev/fuse or a relabel:
# those are for the nested engine, and these are --version and file checks.
set -euxo pipefail

claude --version
claude-supervisor --version
test "$(claude-supervisor --version)" = "claude-supervisor 2.0.0"
claude-agent --version
python3 -c "import sys; assert sys.version_info[:2] >= (3, 14), sys.version"
uv --version
tmux -V
git --version
node --version
pre-commit --version
podman --version
bash -n /usr/local/bin/claude-entrypoint
bash -n /usr/local/bin/claude-worker
test -x /usr/local/bin/claude-worker
test -x /usr/libexec/claude-seat/seat-state
test -x /usr/libexec/claude-seat/ashigaru-hook
# The old names resolve for one release (#41); the old seat hooks do not ship.
test -x /usr/local/bin/developer-entrypoint
test -x /usr/local/bin/developer-worker-claude
test -x /usr/local/bin/developer-skills-sync
test -x /usr/libexec/developer/seat-state
test ! -e /etc/claude-code/managed-settings.d/40-developer-seat.json
ashigaru --help > /dev/null
test "$(rpm -q --qf '%{VERSION}' ashigaru)" = 6.0.2
test "$(python3 -c 'import ashigaru; print(ashigaru.__version__)')" = 6.0.2
test -f /etc/claude-code/.claude/skills/ashigaru/SKILL.md
grep -q '^name: ashigaru$' /etc/claude-code/.claude/skills/ashigaru/SKILL.md
test "$ASHIGARU_URL" = https://ashigaru.crunchtools.com
echo '{}' | /usr/libexec/claude-seat/ashigaru-hook stop
python3 -m json.tool /etc/claude-code/managed-settings.d/40-claude-seat.json > /dev/null
