#!/usr/bin/env python3
"""
Telegram 消息发送工具

用法：
  python3 telegram_send.py -t <token> <chat_id> <topic> "消息内容"
  python3 telegram_send.py -t <token> <topic> "消息内容"  # 使用默认 chat_id

环境变量：
  TELEGRAM_BOT_TOKEN  — Bot token
  TELEGRAM_CHAT_ID    — 目标群组 ID（默认: 见 DEFAULT_CHAT_ID）
"""

import os
import sys
import json
import logging
import urllib.request
import urllib.error
from pathlib import Path

# ── 配置 ─────────────────────────────────────────────────────────
LOG_DIR = Path.home() / ".hermes" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "telegram_send.log"

# Topic 名称 → 数字 ID 映射，按需修改
TOPIC_MAP = {
    # "main":         1387,
    # "agent-watch":  3,
    # "agent-design": 5,
    # "agent-code":   7,
    # "agent-test":   162,
}

# 默认群组 ID，按需修改
DEFAULT_CHAT_ID = ""  # 例如 "-1001234567890"

# ── 日志 ─────────────────────────────────────────────────────────
logger = logging.getLogger("telegram_send")
logger.setLevel(logging.DEBUG)
_fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
_fh.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
logger.addHandler(_fh)


def load_token() -> str:
    """从环境变量或 .env 文件加载 TELEGRAM_BOT_TOKEN"""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        logger.info(f"load_token: from env var, token={token[:10]}...")
        return token

    env_paths = []

    # 1. HERMES_HOME/.env
    hermes_home = os.environ.get("HERMES_HOME")
    if hermes_home:
        env_paths.append(Path(hermes_home) / ".env")

    # 2. ~/.hermes/.env
    env_paths.append(Path.home() / ".hermes" / ".env")

    # 3. All profile .env files
    profiles_dir = Path.home() / ".hermes" / "profiles"
    if profiles_dir.exists():
        for p in sorted(profiles_dir.iterdir()):
            env_file = p / ".env"
            if env_file.exists() and env_file not in env_paths:
                env_paths.append(env_file)

    for env_path in env_paths:
        if not env_path.exists():
            continue
        try:
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("TELEGRAM_BOT_TOKEN=") and not line.startswith("#"):
                        token = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if token:
                            logger.info(f"load_token: from {env_path}, token={token[:10]}...")
                            return token
        except Exception:
            continue

    logger.error("load_token: TELEGRAM_BOT_TOKEN not found")
    print("ERROR: TELEGRAM_BOT_TOKEN not found", file=sys.stderr)
    sys.exit(1)


def resolve_topic_id(topic: str) -> int:
    """将 topic 名称或数字字符串解析为 int"""
    if topic in TOPIC_MAP:
        return TOPIC_MAP[topic]
    try:
        return int(topic)
    except ValueError:
        valid = ", ".join(TOPIC_MAP.keys()) if TOPIC_MAP else "(none defined)"
        print(f"ERROR: Unknown topic '{topic}'. Valid: {valid}", file=sys.stderr)
        sys.exit(1)


def send_message(token: str, chat_id: str, topic_id: int, text: str) -> dict:
    """发送消息到 Telegram topic"""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "message_thread_id": topic_id,
        "text": text,
    }
    data = json.dumps(payload).encode("utf-8")
    logger.info(f"send_message: chat={chat_id} topic={topic_id} text={text[:80]}...")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("ok"):
                msg = result["result"]
                logger.info(f"send_message: OK → topic {topic_id} message_id={msg['message_id']}")
                print(f"OK → topic {topic_id} (message_id={msg['message_id']})")
                return result
            else:
                logger.error(f"send_message: API error: {json.dumps(result, ensure_ascii=False)}")
                print(f"ERROR: {json.dumps(result, ensure_ascii=False)}", file=sys.stderr)
                sys.exit(1)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        logger.error(f"send_message: HTTP {e.code}: {body}")
        print(f"HTTP {e.code}: {body}", file=sys.stderr)
        sys.exit(1)


def main():
    logger.info(f"main: called with argv={sys.argv}")

    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    # Parse -t/--token flag
    token_arg = None
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] in ("-t", "--token"):
            if i + 1 >= len(args):
                print("ERROR: -t requires a token value", file=sys.stderr)
                sys.exit(1)
            token_arg = args[i + 1]
            args = args[:i] + args[i + 2:]
        else:
            i += 1

    token = token_arg or load_token()

    if len(args) < 2:
        print(__doc__.strip())
        sys.exit(1)

    # <chat_id> <topic> <message> 或 <topic> <message>（用默认 chat_id）
    if len(args) >= 3 and (args[0].startswith("-") or args[0].lstrip("-").isdigit()):
        chat_id = args[0]
        topic = args[1]
        message = args[2]
    else:
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", DEFAULT_CHAT_ID)
        topic = args[0]
        message = args[1]

    topic_id = resolve_topic_id(topic)
    send_message(token, chat_id, topic_id, message)


if __name__ == "__main__":
    main()
