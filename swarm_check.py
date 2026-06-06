#!/usr/bin/env python3
"""
swarm_check.py — 檢查 agent 的任務、交付、全局進度。

用途：
- Planner / Producer / Researcher 啟動時：看自己被指派的 active tasks 與 pending handoffs。
- Coordinator：用 --all 看整體進度，作為 Telegram 回報來源。
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TASK_STATUSES = ["inbox", "active", "blocked", "done"]
HANDOFF_STATUSES = ["pending", "accepted", "done"]


def load_json_files(folder: Path) -> list[dict[str, Any]]:
    if not folder.exists():
        return []
    items = []
    for file in sorted(folder.glob("*.json")):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
            data["_file"] = str(file)
            items.append(data)
        except json.JSONDecodeError as exc:
            items.append({
                "id": file.stem,
                "_file": str(file),
                "_error": f"JSON 解析失敗：{exc}",
            })
    return items


def load_tasks(root: Path) -> list[dict[str, Any]]:
    tasks = []
    for status in TASK_STATUSES:
        for item in load_json_files(root / "swarm" / "tasks" / status):
            item.setdefault("status", status)
            item["_kind"] = "task"
            tasks.append(item)
    return tasks


def load_handoffs(root: Path) -> list[dict[str, Any]]:
    handoffs = []
    for status in HANDOFF_STATUSES:
        for item in load_json_files(root / "swarm" / "handoffs" / status):
            item.setdefault("status", status)
            item["_kind"] = "handoff"
            handoffs.append(item)
    return handoffs


def load_status(root: Path) -> list[dict[str, Any]]:
    return load_json_files(root / "swarm" / "status")


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def age_text(value: str | None) -> str:
    dt = parse_dt(value)
    if not dt:
        return "未知"
    if dt.tzinfo is None:
        now = datetime.now()
    else:
        now = datetime.now(timezone.utc)
    delta = now - dt
    seconds = max(0, int(delta.total_seconds()))
    if seconds < 60:
        return f"{seconds} 秒前"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} 分鐘前"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} 小時前"
    return f"{hours // 24} 天前"


def print_task(task: dict[str, Any], prefix: str = "- ") -> None:
    if "_error" in task:
        print(f"{prefix}{task.get('id')}：{task['_error']} ({task.get('_file')})")
        return
    print(f"{prefix}{task.get('id', 'NO-ID')} [{task.get('status', '?')}] {task.get('title', '(無標題)')}")
    print(f"  project: {task.get('project', '-')}; assignee: {task.get('assignee', '-')}; risk: {task.get('risk', '-')}")
    print(f"  goal: {task.get('goal', '-')}")
    if task.get("next_agents"):
        print(f"  next_agents: {', '.join(task['next_agents'])}")
    if task.get("human_review_required"):
        print("  ⚠ 需要 human 審核")
    print(f"  file: {task.get('_file')}")


def print_handoff(handoff: dict[str, Any], prefix: str = "- ") -> None:
    if "_error" in handoff:
        print(f"{prefix}{handoff.get('id')}：{handoff['_error']} ({handoff.get('_file')})")
        return
    print(f"{prefix}{handoff.get('id', 'NO-ID')} [{handoff.get('status', '?')}] {handoff.get('from', '?')} → {handoff.get('to', '?')}")
    print(f"  task: {handoff.get('parent_task', '-')}; risk: {handoff.get('risk', '-')}")
    print(f"  summary: {handoff.get('summary', '-')}")
    print(f"  next_action: {handoff.get('next_action', '-')}")
    if handoff.get("files"):
        print(f"  files: {', '.join(handoff['files'])}")
    if handoff.get("decision_needed"):
        print(f"  ⚠ decision_needed: {handoff['decision_needed']}")
    if handoff.get("human_review_required"):
        print("  ⚠ 需要 human 審核")
    print(f"  file: {handoff.get('_file')}")


def print_agent_view(agent: str, tasks: list[dict[str, Any]], handoffs: list[dict[str, Any]]) -> None:
    assigned = [t for t in tasks if str(t.get("assignee", "")).lower() == agent.lower() and t.get("status") in {"inbox", "active", "blocked"}]
    incoming = [h for h in handoffs if str(h.get("to", "")).lower() == agent.lower() and h.get("status") in {"pending", "accepted"}]
    outgoing = [h for h in handoffs if str(h.get("from", "")).lower() == agent.lower() and h.get("status") in {"pending", "accepted"}]

    print(f"# {agent} 工作檢查")
    print()
    print(f"## 指派給 {agent} 的任務：{len(assigned)}")
    if assigned:
        for task in assigned:
            print_task(task)
    else:
        print("- 無")

    print()
    print(f"## 交付給 {agent} 的 handoff：{len(incoming)}")
    if incoming:
        for handoff in incoming:
            print_handoff(handoff)
    else:
        print("- 無")

    print()
    print(f"## {agent} 尚未完成的對外交付：{len(outgoing)}")
    if outgoing:
        for handoff in outgoing:
            print_handoff(handoff)
    else:
        print("- 無")


def print_global_view(tasks: list[dict[str, Any]], handoffs: list[dict[str, Any]], statuses: list[dict[str, Any]]) -> None:
    print("# Swarm 全局狀態")
    print()
    print("## Tasks")
    for status in TASK_STATUSES:
        count = sum(1 for t in tasks if t.get("status") == status)
        print(f"- {status}: {count}")
    print()
    for task in [t for t in tasks if t.get("status") in {"active", "blocked", "inbox"}]:
        print_task(task)

    print()
    print("## Handoffs")
    for status in HANDOFF_STATUSES:
        count = sum(1 for h in handoffs if h.get("status") == status)
        print(f"- {status}: {count}")
    print()
    for handoff in [h for h in handoffs if h.get("status") in {"pending", "accepted"}]:
        print_handoff(handoff)

    print()
    print("## Agent status")
    if statuses:
        for status in statuses:
            name = status.get("agent", Path(status.get("_file", "unknown")).stem)
            updated = status.get("updated_at") or status.get("timestamp")
            state = status.get("state", status.get("status", "unknown"))
            print(f"- {name}: {state}; updated: {age_text(updated)}; file: {status.get('_file')}")
    else:
        print("- 無 status/*.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Swarm Framework v0.1.0 — 檢查 swarm 工作狀態")
    parser.add_argument("--path", default=".", help="AI_ControlCenter / ai-framework-v3 根目錄，預設目前目錄")
    parser.add_argument("--agent", required=True, help="Agent 名稱，例如 Coordinator / Planner / Producer / Researcher")
    parser.add_argument("--all", action="store_true", help="顯示全局狀態，適合 Coordinator 使用")
    args = parser.parse_args()

    root = Path(args.path).expanduser()
    if not root.exists():
        print(f"❌ 路徑不存在：{root}", file=sys.stderr)
        sys.exit(1)

    tasks = load_tasks(root)
    handoffs = load_handoffs(root)
    statuses = load_status(root)

    if args.all:
        print_global_view(tasks, handoffs, statuses)
        print()

    print_agent_view(args.agent, tasks, handoffs)


if __name__ == "__main__":
    main()
