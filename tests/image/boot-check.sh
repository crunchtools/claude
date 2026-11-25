#!/usr/bin/env bash
# The image's boot gate, run inside the image this PR builds (the boot-gate check
# in pyproject.toml). It was `boot-command` in [tool.sdlc.image], which sdlc does
# not enforce (crunchtools/sdlc#118). Nothing here needs /dev/fuse or a relabel:
# those are for the nested engine, and these are --version and file checks.
set -euxo pipefail

claude --version
claude-agent --version
python3 -c "import sys; assert sys.version_info[:2] >= (3, 14), sys.version"
uv --version
tmux -V
git --version
node --version
pre-commit --version
podman --version
bash -n /usr/local/bin/developer-entrypoint
bash -n /usr/local/bin/developer-worker-claude
test -x /usr/local/bin/developer-worker-claude
test -x /usr/libexec/developer/seat-state
test -x /usr/libexec/developer/ashigaru-hook
ashigaru --help > /dev/null
test "$(rpm -q --qf '%{VERSION}' ashigaru)" = 5.3.0
test "$(python3 -c 'import ashigaru; print(ashigaru.__version__)')" = 5.3.0
test -f /etc/claude-code/.claude/skills/ashigaru/SKILL.md
grep -q '^name: ashigaru$' /etc/claude-code/.claude/skills/ashigaru/SKILL.md
test "$ASHIGARU_URL" = https://ashigaru.crunchtools.com
echo '{}' | /usr/libexec/developer/ashigaru-hook stop
python3 -m json.tool /etc/claude-code/managed-settings.d/40-developer-seat.json > /dev/null
