#!/usr/bin/env python3
"""
swarm_create_handoff.py — 建立 agent 之間的 file-based handoff。

設計原則：
- 只新增 JSON handoff 檔，不覆寫既有檔案。
- 預設建立到 swarm/handoffs/pending/。
- handoff 是 agent 互相交付工作的真相來源，不用私人聊天當紀錄。
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

VALID_STATUSES = {"pending", "accepted", "done"}
VALID_RISKS = {"low", "medium", "high"}


def ensure_dirs(root: Path) -> None:
    for rel in [
        "swarm/handoffs/pending",
        "swarm/handoffs/accepted",
        "swarm/handoffs/done",
        "swarm/outputs",
    ]:
        (root / rel).mkdir(parents=True, exist_ok=True)


def next_id(folder: Path, prefix: str) -> str:
    today = datetime.now().strftime("%Y%m%d")
    pattern = f"{prefix}-{today}-*.json"
    max_num = 0
    for file in folder.glob(pattern):
        match = re.search(r"-(\d{3,})\.json$", file.name)
        if match:
            max_num = max(max_num, int(match.group(1)))
    return f"{prefix}-{today}-{max_num + 1:03d}"


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff_-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "handoff"


def split_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    result = []
    for value in values:
        for item in value.split(","):
            item = item.strip()
            if item:
                result.append(item)
    return result


def write_json_new(path: Path, data: dict) -> None:
    if path.exists():
        raise FileExistsError(f"目標檔案已存在，不覆寫：{path}")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Swarm Framework v0.1.0 — 建立 swarm handoff")
    parser.add_argument("--path", default=".", help="AI_ControlCenter / ai-framework-v3 根目錄，預設目前目錄")
    parser.add_argument("--from-agent", required=True, help="交付來源 agent，例如 Planner")
    parser.add_argument("--to-agent", required=True, help="接收 agent，例如 Producer")
    parser.add_argument("--task", required=True, help="父任務 ID，例如 TASK-20260606-001")
    parser.add_argument("--summary", required=True, help="已完成什麼")
    parser.add_argument("--next-action", required=True, help="接收者下一步要做什麼")
    parser.add_argument("--status", default="pending", choices=sorted(VALID_STATUSES), help="交付狀態")
    parser.add_argument("--risk", default="low", choices=sorted(VALID_RISKS), help="風險等級")
    parser.add_argument("--human-review-required", action="store_true", help="是否需要人工審核")
    parser.add_argument("--file", action="append", help="相關檔案路徑，可重複")
    parser.add_argument("--acceptance", action="append", help="驗收條件，可重複")
    parser.add_argument("--decision-needed", default=None, help="需要 Human 決策的問題，沒有則省略")
    parser.add_argument("--notes", default="", help="補充說明")
    args = parser.parse_args()

    root = Path(args.path).expanduser()
    if not root.exists():
        print(f"❌ 路徑不存在：{root}", file=sys.stderr)
        sys.exit(1)

    ensure_dirs(root)
    target_dir = root / "swarm" / "handoffs" / args.status
    handoff_id = next_id(target_dir, "HANDOFF")
    now = datetime.now().isoformat(timespec="seconds")

    handoff = {
        "id": handoff_id,
        "from": args.from_agent,
        "to": args.to_agent,
        "parent_task": args.task,
        "status": args.status,
        "created_at": now,
        "updated_at": now,
        "summary": args.summary,
        "next_action": args.next_action,
        "files": split_list(args.file),
        "acceptance_criteria": args.acceptance or [],
        "decision_needed": args.decision_needed,
        "risk": args.risk,
        "human_review_required": bool(args.human_review_required),
        "notes": args.notes,
    }

    filename = f"{handoff_id}_{slugify(args.from_agent)}_to_{slugify(args.to_agent)}.json"
    target = target_dir / filename
    write_json_new(target, handoff)
    print(f"✅ 已建立交付：{handoff_id}")
    print(f"🔁 {args.from_agent} → {args.to_agent}")
    print(f"📄 {target}")


if __name__ == "__main__":
    main()
