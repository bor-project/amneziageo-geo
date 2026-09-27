#!/usr/bin/env bash
# Publishes the files of the build folder as a commit on the release branch of the remote.
set -euo pipefail

remote=$1
out=$(cd "${2:-out}" && pwd)
source_sha=${GITHUB_SHA:-local}
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

cd "$work"
git init -q
git remote add origin "$remote"
git symbolic-ref HEAD refs/heads/release
if git fetch -q --depth=1 origin release 2>/dev/null; then
  git update-ref refs/heads/release FETCH_HEAD
fi

cp "$out"/* .
git add -A
if git rev-parse -q --verify HEAD >/dev/null && git diff --cached --quiet HEAD; then
  echo "release is up to date"
  exit 0
fi

git -c user.name=bor -c user.email=bor-project@users.noreply.github.com \
  commit -q -m "Publish lists of ${source_sha:0:7}"
git push -q origin release
echo "published $(git rev-parse --short HEAD) to release"
