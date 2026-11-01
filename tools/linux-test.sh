#!/bin/sh
# Installs nekofetch with pipx in Linux containers and runs it.
#   tools/linux-test.sh [image...]    default: debian:trixie fedora:latest alpine:latest
set -eu
cd "$(dirname "$0")/.."
[ $# -gt 0 ] || set -- debian:trixie fedora:latest alpine:latest
for image in "$@"; do
  printf '\n=== %s\n' "$image"
  docker run --rm -v "$PWD:/src:ro" -e TERM=xterm-256color "$image" sh -ec '
    if command -v apt-get >/dev/null; then
      apt-get update -qq >/dev/null && apt-get install -y -qq fastfetch chafa pipx >/dev/null 2>&1
    elif command -v dnf >/dev/null; then
      dnf install -y -q fastfetch chafa pipx >/dev/null 2>&1
    elif command -v apk >/dev/null; then
      apk add -q fastfetch chafa pipx
    fi
    cp -r /src /root/nekofetch
    pipx install --quiet /root/nekofetch >/dev/null
    export PATH="$HOME/.local/bin:$PATH"
    SHELL=/bin/bash nekofetch setup --yes
    nekofetch doctor | grep -E "fastfetch|protocol|terminal"
    nekofetch -p ascii -- --pipe | head -12
    nekofetch -p chafa -- --pipe | head -2 | cut -c1-100
    nekofetch setup --undo | head -1
  '
done
