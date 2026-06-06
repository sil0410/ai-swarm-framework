#!/usr/bin/env python3
"""
swarm_create_task.py — 建立 file-based swarm 任務。

設計原則：
- 只新增 JSON 任務檔，不覆寫既有檔案。
- 預設建立到 swarm/tasks/active/。
- 可用 --status inbox/active/blocked/done 指定初始狀態。
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

VALID_STATUSES = {"inbox", "active", "blocked", "done"}
VALID_RISKS = {"low", "medium", "high"}


def ensure_dirs(root: Path) -> None:
    for rel in [
        "swarm/tasks/inbox",
        "swarm/tasks/active",
        "swarm/tasks/blocked",
        "swarm/tasks/done",
        "swarm/handoffs/pending",
        "swarm/handoffs/accepted",
        "swarm/handoffs/done",
        "swarm/status",
        "swarm/outputs",
    ]:
        (root / rel).mkdir(parents=True, exist_ok=True)


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff_-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "task"


def next_id(folder: Path, prefix: str) -> str:
    today = datetime.now().strftime("%Y%m%d")
    pattern = f"{prefix}-{today}-*.json"
    max_num = 0
    for file in folder.glob(pattern):
        match = re.search(r"-(\d{3,})\.json$", file.name)
        if match:
            max_num = max(max_num, int(match.group(1)))
    return f"{prefix}-{today}-{max_num + 1:03d}"


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
    parser = argparse.ArgumentParser(description="AI Swarm Framework v0.1.0 — 建立 swarm 任務")
    parser.add_argument("--path", default=".", help="AI_ControlCenter / ai-framework-v3 根目錄，預設目前目錄")
    parser.add_argument("--project", required=True, help="專案名稱，例如 demo")
    parser.add_argument("--title", required=True, help="任務標題")
    parser.add_argument("--assignee", required=True, help="指派 agent，例如 Coordinator / Planner / Producer / Researcher")
    parser.add_argument("--goal", required=True, help="成功標準 / 目標")
    parser.add_argument("--created-by", default="Human", help="建立者，預設 Human")
    parser.add_argument("--status", default="active", choices=sorted(VALID_STATUSES), help="初始狀態")
    parser.add_argument("--risk", default="low", choices=sorted(VALID_RISKS), help="風險等級")
    parser.add_argument("--human-review-required", action="store_true", help="是否需要人工審核")
    parser.add_argument("--depends-on", action="append", help="依賴任務 ID，可重複或逗號分隔")
    parser.add_argument("--next-agent", action="append", help="後續可能接手 agent，可重複或逗號分隔")
    parser.add_argument("--acceptance", action="append", help="驗收條件，可重複")
    parser.add_argument("--file", action="append", help="相關檔案路徑，可重複")
    parser.add_argument("--notes", default="", help="補充說明")
    args = parser.parse_args()

    root = Path(args.path).expanduser()
    if not root.exists():
        print(f"❌ 路徑不存在：{root}", file=sys.stderr)
        sys.exit(1)

    ensure_dirs(root)
    target_dir = root / "swarm" / "tasks" / args.status
    task_id = next_id(target_dir, "TASK")
    now = datetime.now().isoformat(timespec="seconds")

    task = {
        "id": task_id,
        "title": args.title,
        "project": args.project,
        "assignee": args.assignee,
        "status": args.status,
        "created_by": args.created_by,
        "created_at": now,
        "updated_at": now,
        "depends_on": split_list(args.depends_on),
        "next_agents": split_list(args.next_agent),
        "goal": args.goal,
        "acceptance_criteria": args.acceptance or [],
        "files": args.file or [],
        "risk": args.risk,
        "human_review_required": bool(args.human_review_required),
        "notes": args.notes,
    }

    filename = f"{task_id}_{slugify(args.project)}_{slugify(args.title)}.json"
    target = target_dir / filename
    write_json_new(target, task)
    print(f"✅ 已建立任務：{task_id}")
    print(f"📄 {target}")


if __name__ == "__main__":
    main()
