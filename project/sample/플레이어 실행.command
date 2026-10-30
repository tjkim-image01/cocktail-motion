#!/bin/zsh
cd "$(dirname "$0")"
open http://127.0.0.1:4343/
node server.mjs
