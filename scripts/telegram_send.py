#!/usr/bin/env python3
"""
Telegram 消息发送工具（内部工具，请通过 send_to_agent-*.sh 脚本调用）

直接用法（需提供 token）：
  python3 telegram_send.py -t <token> <topic> "消息内容"
  python3 telegram_send.py -t <token> <chat_id> <topic> "消息内容"

环境变量：
  TELEGRAM_BOT_TOKEN  — Bot token
  TELEGRAM_CHAT_ID    — 目标群组 ID
"""

import os
import sys
import json
import logging
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

# ── 日志配置 ─────────────────────────────────────────────────────
LOG_DIR = Path("/root/.hermes/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "telegram_send.log"

logger = logging.getLogger("telegram_send")
logger.setLevel(logging.DEBUG)

_fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
_fh.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
logger.addHandler(_fh)

# ── 团队 Topic 映射 ──────────────────────────────────────────────
TOPIC_MAP = {
    "agent-watch":  3,
    "agent-design": 5,
    "agent-code":   7,
    "agent-test":   162,
}

DEFAULT_CHAT_ID = "-1003300933525"


def load_token() -> str:
    """从环境变量或 .env 文件加载 TELEGRAM_BOT_TOKEN"""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        logger.info(f"load_token: from env var, token={token[:10]}...")
        return token

    # Collect .env files in priority order
    env_paths = []

    # 1. HERMES_HOME/.env (current profile — highest priority among files)
    hermes_home = os.environ.get("HERMES_HOME")
    if hermes_home:
        hermes_env = Path(hermes_home) / ".env"
        if hermes_env.exists():
            env_paths.append(hermes_env)
            logger.info(f"load_token: HERMES_HOME={hermes_home}, checking {hermes_env}")

    # 2. ~/.hermes/.env (sandbox HOME — may be wrong)
    env_paths.append(Path.home() / ".hermes" / ".env")

    # 3. /root/.hermes/.env (real HOME fallback)
    real_hermes = Path("/root/.hermes")
    real_env = real_hermes / ".env"
    if real_env.exists():
        env_paths.append(real_env)

    # 4. All profile .env files (last resort)
    profiles_dir = Path.home() / ".hermes" / "profiles"
    real_profiles_dir = real_hermes / "profiles"
    for search_dir in [profiles_dir, real_profiles_dir]:
        if search_dir.exists():
            for p in sorted(search_dir.iterdir()):
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

    logger.error("load_token: TELEGRAM_BOT_TOKEN not found in any source")
    print("ERROR: TELEGRAM_BOT_TOKEN not found", file=sys.stderr)
    sys.exit(1)


def resolve_topic_id(topic: str) -> int:
    if topic in TOPIC_MAP:
        return TOPIC_MAP[topic]
    try:
        return int(topic)
    except ValueError:
        print(f"ERROR: Unknown topic '{topic}'. Valid: {', '.join(TOPIC_MAP.keys())}", file=sys.stderr)
        sys.exit(1)


def send_message(token: str, chat_id: str, topic_id: int, text: str) -> dict:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "message_thread_id": topic_id,
        "text": text,
        "parse_mode": "HTML",
    }
    data = json.dumps(payload).encode("utf-8")
    logger.info(f"send_message: chat={chat_id} topic={topic_id} token={token[:10]}... text={text[:80]}...")
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
    source = "-t flag" if token_arg else "load_token()"
    logger.info(f"main: token_arg={token_arg!r}, source={source}, final_token={token[:10]}...")

    if len(args) < 2:
        print(__doc__.strip())
        sys.exit(1)

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
