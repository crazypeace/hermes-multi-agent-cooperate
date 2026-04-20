#!/bin/bash
# 发送消息给 agent-code
# 用法: bash send_to_agent-code.sh "消息内容"
# FROM/TO/CONTENT 格式由脚本自动包装

set -euo pipefail

# 读取当前 profile 的 bot token
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$(dirname "$SCRIPT_DIR")/.env"

TOKEN=$(grep '^TELEGRAM_BOT_TOKEN=' "$ENV_FILE" | cut -d= -f2 | tr -d "\"'")

if [ -z "$TOKEN" ]; then
  echo "ERROR: TELEGRAM_BOT_TOKEN not found in $ENV_FILE" >&2
  exit 1
fi

CONTENT="${1:?用法: $0 \"消息内容\"}"

# FROM = 当前 profile，TO = 目标 agent
FROM="agent-watch"
TO="agent-code"

FORMATTED_MSG="FROM: $FROM
TO: $TO
CONTENT:
$CONTENT"

python3 /root/.hermes/scripts/telegram_send.py -t "$TOKEN" -1003300933525 7 "$FORMATTED_MSG"
