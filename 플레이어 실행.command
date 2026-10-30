#!/bin/zsh
cd "$(dirname "$0")"
node project/sample/server.mjs &
cocktail_server_pid=$!
trap 'kill "$cocktail_server_pid" 2>/dev/null' EXIT INT TERM
for attempt in {1..30}; do
  if curl -fsS 'http://127.0.0.1:4343/' >/dev/null 2>&1; then
    open 'http://127.0.0.1:4343/'
    break
  fi
  sleep 0.1
done
wait "$cocktail_server_pid"
