#!/usr/bin/env python3
"""
bootstrap_agent.py — 無狀態身份註冊與 Inbox 寫入機制

設計理念：
  本機端不儲存狀態，所有 Agent 身份與專案記憶皆存於中央 NAS。
  Agent 產出的任何結果，只能以「新增檔案」的方式寫入 inbox/，
  絕對不覆寫既有主檔。

使用方式：
  python bootstrap_agent.py --identity leo --nas-path Z:\\AI_ControlCenter
  python bootstrap_agent.py --identity mikey --nas-path /mnt/nas/AI_ControlCenter
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def load_identity(nas_root: Path, identity_name: str) -> dict:
    """從 NAS 讀取 agent 身份設定檔"""
    identity_file = nas_root / "identities" / f"{identity_name}.json"

    if not identity_file.exists():
        print(f"❌ 找不到身份檔：{identity_file}")
        print(f"   可用的身份：")
        identities_dir = nas_root / "identities"
        if identities_dir.exists():
            for f in identities_dir.glob("*.json"):
                print(f"     - {f.stem}")
        else:
            print(f"   ⚠️  identities/ 目錄不存在，請先執行 setup.py")
        sys.exit(1)

    with open(identity_file, encoding="utf-8") as f:
        identity = json.load(f)

    print(f"✅ 身份載入：{identity.get('name', identity_name)}")
    print(f"   職能：{identity.get('role', '未定義')}")
    print(f"   設備：{identity.get('device', '未指定')}")
    return identity


def ensure_inbox(nas_root: Path):
    """確保 inbox/ 目錄存在"""
    inbox = nas_root / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    return inbox


def write_to_inbox(
    nas_root: Path,
    project_name: str,
    content: str,
    agent_name: str,
    tags: list = None
) -> Path:
    """
    安全寫入函數：以「新增檔案」方式寫入 inbox/

    檔案命名規則：{project}_{timestamp}_{agent}.md
    例如：demo_20260602_143000_leo.md

    絕對不覆寫。如果同名檔案已存在（同一秒內多次呼叫），
    自動加上計數後綴。
    """
    inbox = ensure_inbox(nas_root)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{project_name}_{timestamp}_{agent_name}"

    # 防止同秒衝突
    target = inbox / f"{base_name}.md"
    counter = 1
    while target.exists():
        target = inbox / f"{base_name}_{counter}.md"
        counter += 1

    # 組裝內容
    tags_line = ""
    if tags:
        tags_line = f"tags: [{', '.join(tags)}]\n"

    file_content = f"""---
project: {project_name}
agent: {agent_name}
timestamp: {datetime.now().isoformat()}
{tags_line}---

{content}
"""

    target.write_text(file_content, encoding="utf-8")
    print(f"📝 已寫入：{target.name}")
    return target


def show_status(nas_root: Path, identity: dict):
    """顯示目前 inbox 內該 agent 的待處理項目"""
    inbox = nas_root / "inbox"
    if not inbox.exists():
        print("📭 inbox/ 為空")
        return

    agent_name = identity.get("name", "unknown")
    files = sorted(inbox.glob(f"*_{agent_name}.md"), reverse=True)

    if not files:
        print(f"📭 {agent_name} 在 inbox 中沒有待處理項目")
        return

    print(f"\n📬 {agent_name} 的 inbox 項目（最新 10 筆）：")
    for f in files[:10]:
        print(f"   {f.name}")


def main():
    parser = argparse.ArgumentParser(
        description="AI 協作框架 — Agent 身份註冊與 Inbox 寫入"
    )
    parser.add_argument(
        "--identity", required=True,
        help="Agent 身份名稱（對應 identities/ 下的 JSON 檔名）"
    )
    parser.add_argument(
        "--nas-path", required=True,
        help="NAS 中央架構路徑"
    )
    parser.add_argument(
        "--write", nargs=3, metavar=("PROJECT", "CONTENT", "AGENT"),
        help="寫入 inbox：--write demo '完成盤點' leo"
    )
    parser.add_argument(
        "--status", action="store_true",
        help="顯示該 agent 的 inbox 狀態"
    )
    args = parser.parse_args()

    nas_root = Path(args.nas_path)
    if not nas_root.exists():
        print(f"❌ NAS 路徑不存在：{nas_root}")
        sys.exit(1)

    identity = load_identity(nas_root, args.identity)
    ensure_inbox(nas_root)

    if args.write:
        project, content, agent = args.write
        write_to_inbox(nas_root, project, content, agent)
    elif args.status:
        show_status(nas_root, identity)
    else:
        # 預設行為：顯示身份 + inbox 狀態
        show_status(nas_root, identity)
        print(f"\n💡 使用方式：")
        print(f"   寫入：python bootstrap_agent.py --identity {args.identity} "
              f"--nas-path {args.nas_path} --write demo '完成任務' {identity.get('name', args.identity)}")


if __name__ == "__main__":
    main()
