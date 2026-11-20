#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$DIR"

if [ ! -d ".venv" ]; then
    echo "正在建立 Python 虛擬環境..."
    python3 -m venv .venv
    ./.venv/bin/pip install -r requirements.txt
fi

echo "🚀 正在啟動信用卡付款小幫手 Web 服務 (http://localhost:8000)..."
./.venv/bin/python app.py
