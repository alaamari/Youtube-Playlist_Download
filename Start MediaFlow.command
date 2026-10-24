#!/bin/zsh
cd "${0:A:h}"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if [[ -x .venv/bin/python ]]; then
  .venv/bin/python engine/app.py
else
  python3 engine/app.py
fi
