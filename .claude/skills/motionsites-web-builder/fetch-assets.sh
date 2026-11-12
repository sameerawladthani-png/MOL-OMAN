#!/usr/bin/env bash
# Downloads the skill's examples/ and media/ folders from the official
# MotionSites repository. They are not committed here because their license
# does not allow redistribution (see LICENSE, section 2).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
rev="faa30d512e3973e58675c72101a7ef42ed37ae83"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
git clone --quiet https://github.com/Motionsites-AI/claude-skill.git "$tmp/src"
git -C "$tmp/src" checkout --quiet "$rev"
skill="$tmp/src/plugins/motionsites-web-builder/skills/motionsites-web-builder"
rm -rf "$here/examples" "$here/media"
cp -r "$skill/examples" "$skill/media" "$here/"
echo "MotionSites examples and media installed in $here"
