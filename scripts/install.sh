#!/bin/zsh
# Install Doc-image-deck（文图方案）for Claude Code and Codex, then set up the runtime.
#   install.sh [--no-setup]
# The skill files are copied to ~/.agents/skills/doc-image-deck; ~/.claude/skills and ~/.codex/skills get symlinks
# to it, so both hosts read the same copy. Rerun after editing the repository.
SRC=${0:A:h:h}
NAME=doc-image-deck
DEST=$HOME/.agents/skills/$NAME
mkdir -p $DEST
rsync -a --delete --exclude '__pycache__' --exclude '*.pyc' --exclude '.DS_Store' \
  "$SRC/SKILL.md" "$SRC/LICENSE" "$SRC/agents" "$SRC/references" "$SRC/scripts" "$DEST/"
chmod +x $DEST/scripts/deck $DEST/scripts/*.sh $DEST/scripts/editable/*.sh
for host in $HOME/.claude/skills $HOME/.codex/skills; do
  mkdir -p $host
  if [[ -e $host/$NAME && ! -L $host/$NAME ]]; then mv $host/$NAME $host/$NAME.bak.$(date +%s); fi
  ln -sfn ../../.agents/skills/$NAME $host/$NAME
  echo "已链接：$host/$NAME -> $DEST"
done
[[ $1 == --no-setup ]] || zsh $DEST/scripts/setup.sh
