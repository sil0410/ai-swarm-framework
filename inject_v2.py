#!/usr/bin/env python3
"""
inject_v2.py — 動態上下文組裝引擎

設計理念：
  讀取 project 的 YAML Frontmatter 標籤，自動比對並縫合所需的 skills。
  輸出完整的 Context 文本，只包含相關內容，不包含冗餘資訊。

安裝依賴：
  pip install pyyaml

使用方式：
  python inject_v2.py --path C:\\AI_ControlCenter --project demo
  python inject_v2.py --path ~/AI_ControlCenter --project demo --copy
  python inject_v2.py --path ~/AI_ControlCenter --project demo --out context.md
"""

import argparse
import json
import re
import sys
from pathlib import Path
from datetime import datetime

try:
    import yaml
except ImportError:
    print("❌ 需要安裝 pyyaml：pip install pyyaml")
    sys.exit(1)


# ─────────────────────────────────────────
# Frontmatter 解析
# ─────────────────────────────────────────
FRONTMATTER_PATTERN = re.compile(
    r"^\s*---\s*\n(.*?)\n---\s*",
    re.DOTALL
)

def parse_frontmatter(file_path: Path) -> tuple:
    """
    解析 .md 檔案的 YAML Frontmatter。

    回傳 (metadata: dict, body: str)
    - metadata: frontmatter 的 YAML 內容
    - body: frontmatter 之後的正文
    """
    content = file_path.read_text(encoding="utf-8")
    match = FRONTMATTER_PATTERN.match(content)

    if match:
        try:
            metadata = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            metadata = {}
        body = content[match.end():].strip()
    else:
        metadata = {}
        body = content.strip()

    return metadata, body


# ─────────────────────────────────────────
# Skills 掃描與標籤比對
# ─────────────────────────────────────────
def scan_skills(skills_dir: Path) -> dict:
    """
    掃描 skills/ 目錄下所有 .md 檔案，
    建立 skill_id → (metadata, body, path) 的索引。
    """
    index = {}

    if not skills_dir.exists():
        return index

    for md_file in skills_dir.rglob("*.md"):
        if md_file.name.startswith("_"):
            continue

        metadata, body = parse_frontmatter(md_file)
        skill_id = metadata.get("skill_id")

        if skill_id:
            index[skill_id] = {
                "metadata": metadata,
                "body": body,
                "path": md_file
            }

    return index


def match_skills(required: list, skill_index: dict) -> list:
    """
    比對專案所需的 skills 與可用的 skills。
    回傳匹配的 skill 列表。
    """
    matched = []
    missing = []

    for skill_id in required:
        if skill_id in skill_index:
            matched.append(skill_index[skill_id])
        else:
            missing.append(skill_id)

    if missing:
        print(f"⚠️  以下 skills 未找到：{', '.join(missing)}", file=sys.stderr)

    return matched


# ─────────────────────────────────────────
# Inbox 掃描
# ─────────────────────────────────────────
def get_recent_inbox(inbox_dir: Path, project_name: str, max_items: int = 5) -> list:
    """
    取得 inbox/ 中屬於指定專案的最新日誌。
    按時間倒序排列，最多取 max_items 筆。
    """
    if not inbox_dir.exists():
        return []

    files = sorted(
        inbox_dir.glob(f"{project_name}_*.md"),
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )

    results = []
    for f in files[:max_items]:
        _, body = parse_frontmatter(f)
        results.append({
            "filename": f.name,
            "body": body
        })

    return results


# ─────────────────────────────────────────
# Swarm 工作交付掃描
# ─────────────────────────────────────────
def _load_json_files(folder: Path) -> list:
    if not folder.exists():
        return []

    items = []
    for json_file in sorted(folder.glob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            data["_file"] = str(json_file)
            items.append(data)
        except json.JSONDecodeError as exc:
            items.append({
                "id": json_file.stem,
                "_file": str(json_file),
                "_error": f"JSON 解析失敗：{exc}"
            })
    return items


def get_swarm_work(root: Path, agent_name: str, project_name: str = None) -> dict:
    """
    取得指派給 agent 的 active/blocked/inbox tasks，以及交付給 agent 的 pending/accepted handoffs。
    project_name 有值時只保留該 project 的 tasks；handoff 會依 parent_task 對應 project 過濾。
    """
    if not agent_name:
        return {"tasks": [], "handoffs": []}

    all_task_projects = {}
    tasks = []
    for status in ["inbox", "active", "blocked"]:
        for item in _load_json_files(root / "swarm" / "tasks" / status):
            item.setdefault("status", status)
            all_task_projects[item.get("id")] = item.get("project")
            if str(item.get("assignee", "")).lower() == agent_name.lower():
                tasks.append(item)

    if project_name:
        tasks = [t for t in tasks if str(t.get("project", "")).lower() == project_name.lower()]

    handoffs = []
    for status in ["pending", "accepted"]:
        for item in _load_json_files(root / "swarm" / "handoffs" / status):
            item.setdefault("status", status)
            if str(item.get("to", "")).lower() != agent_name.lower():
                continue
            if project_name:
                parent_task = item.get("parent_task")
                if all_task_projects.get(parent_task) != project_name:
                    continue
            handoffs.append(item)

    return {"tasks": tasks, "handoffs": handoffs}


def format_swarm_work(work: dict, agent_name: str) -> str:
    lines = ["---", "", f"# Swarm 工作交付：{agent_name}", ""]

    tasks = work.get("tasks", [])
    lines.append(f"## 指派任務（{len(tasks)}）")
    if tasks:
        for task in tasks:
            lines.append(f"- {task.get('id', 'NO-ID')} [{task.get('status', '?')}] {task.get('title', '(無標題)')}")
            lines.append(f"  - project: {task.get('project', '-')}")
            lines.append(f"  - goal: {task.get('goal', '-')}")
            if task.get("_error"):
                lines.append(f"  - error: {task['_error']}")
            if task.get("_file"):
                lines.append(f"  - file: {task['_file']}")
    else:
        lines.append("- 無")

    handoffs = work.get("handoffs", [])
    lines.append("")
    lines.append(f"## 交付給你的 Handoff（{len(handoffs)}）")
    if handoffs:
        for handoff in handoffs:
            lines.append(f"- {handoff.get('id', 'NO-ID')} [{handoff.get('status', '?')}] {handoff.get('from', '?')} → {handoff.get('to', '?')}")
            lines.append(f"  - parent_task: {handoff.get('parent_task', '-')}")
            lines.append(f"  - summary: {handoff.get('summary', '-')}")
            lines.append(f"  - next_action: {handoff.get('next_action', '-')}")
            if handoff.get("files"):
                lines.append(f"  - files: {', '.join(handoff['files'])}")
            if handoff.get("decision_needed"):
                lines.append(f"  - decision_needed: {handoff['decision_needed']}")
            if handoff.get("human_review_required"):
                lines.append("  - ⚠ 需要 human 審核")
            if handoff.get("_error"):
                lines.append(f"  - error: {handoff['_error']}")
            if handoff.get("_file"):
                lines.append(f"  - file: {handoff['_file']}")
    else:
        lines.append("- 無")

    return "\n".join(lines)


# ─────────────────────────────────────────
# Context 組裝
# ─────────────────────────────────────────
def assemble_context(
    root: Path,
    project_name: str,
    max_inbox: int = 5,
    agent_name: str = None
) -> str:
    """
    組裝完整的 Context 字串。

    順序：
    1. CORE.md
    2. AGENTS.md
    3. projects/{project_name}.md
    4. 根據 project 的 required_skills 自動匹配的 skills
    5. inbox/ 中該專案的最新日誌
    """
    sections = []
    stats = {"skills_matched": 0, "inbox_items": 0}

    # ── 1. CORE.md ──
    core_file = root / "CORE.md"
    if core_file.exists():
        sections.append(core_file.read_text(encoding="utf-8"))
    else:
        sections.append("[⚠️ CORE.md 不存在]")

    # ── 2. AGENTS.md ──
    agents_file = root / "AGENTS.md"
    if agents_file.exists():
        sections.append(agents_file.read_text(encoding="utf-8"))
    else:
        sections.append("[⚠️ AGENTS.md 不存在]")

    # ── 3. Project 主檔 ──
    project_file = root / "projects" / f"{project_name}.md"
    if project_file.exists():
        proj_meta, proj_body = parse_frontmatter(project_file)
        sections.append(f"# 專案：{project_name}\n\n{proj_body}")
    else:
        print(f"❌ 專案檔不存在：{project_file}", file=sys.stderr)
        sections.append(f"[⚠️ projects/{project_name}.md 不存在]")
        proj_meta = {}

    # ── 4. Skills 標籤比對 ──
    required_skills = proj_meta.get("required_skills", [])

    if required_skills:
        skill_index = scan_skills(root / "skills")
        matched = match_skills(required_skills, skill_index)
        stats["skills_matched"] = len(matched)

        if matched:
            skills_section = ["---", "", "# 相關技能手冊", ""]
            for skill in matched:
                meta = skill["metadata"]
                skill_name = meta.get("name", meta.get("skill_id", "未命名"))
                skills_section.append(f"## {skill_name}")
                skills_section.append("")
                skills_section.append(skill["body"])
                skills_section.append("")
            sections.append("\n".join(skills_section))

    # ── 5. Swarm 工作交付（可選） ──
    if agent_name:
        swarm_work = get_swarm_work(root, agent_name, project_name)
        if swarm_work["tasks"] or swarm_work["handoffs"]:
            sections.append(format_swarm_work(swarm_work, agent_name))

    # ── 6. Inbox 最新日誌 ──
    inbox_items = get_recent_inbox(root / "inbox", project_name, max_inbox)
    stats["inbox_items"] = len(inbox_items)

    if inbox_items:
        inbox_section = ["---", "", "# 最新 Inbox 日誌", ""]
        for item in inbox_items:
            inbox_section.append(f"### {item['filename']}")
            inbox_section.append("")
            inbox_section.append(item["body"])
            inbox_section.append("")
        sections.append("\n".join(inbox_section))

    # ── 組裝 ──
    divider = "\n\n" + "─" * 50 + "\n\n"
    full_context = divider.join(sections)

    # ── 尾部標記 ──
    full_context += f"""

{'─' * 50}
[Context 組裝完成]
  專案：{project_name}
  Agent：{agent_name or '未指定'}
  技能匹配：{stats['skills_matched']} 個
  Inbox 日誌：{stats['inbox_items']} 筆
  組裝時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

請依 CORE.md 第 5 節 SOP 進行確認後開始工作。
"""

    return full_context


# ─────────────────────────────────────────
# 主程式
# ─────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="AI 協作框架 — 動態上下文組裝引擎"
    )
    parser.add_argument("--path", required=True, help="架構根目錄路徑")
    parser.add_argument("--project", required=True, help="專案名稱")
    parser.add_argument("--agent", help="Agent 名稱；指定後會納入 swarm tasks/handoffs")
    parser.add_argument("--max-inbox", type=int, default=5,
                        help="最多包含幾筆 inbox 日誌（預設 5）")
    parser.add_argument("--out", help="輸出到檔案（不指定則輸出到終端）")
    parser.add_argument("--copy", action="store_true",
                        help="複製到剪貼簿（需安裝 pyperclip）")
    parser.add_argument("--quiet", action="store_true",
                        help="安靜模式，只輸出 context 不輸出狀態訊息")
    args = parser.parse_args()

    root = Path(args.path)
    if not root.exists():
        print(f"❌ 路徑不存在：{root}")
        sys.exit(1)

    context = assemble_context(root, args.project, args.max_inbox, args.agent)

    if args.out:
        out_path = Path(args.out)
        out_path.write_text(context, encoding="utf-8")
        if not args.quiet:
            print(f"✅ Context 已寫入：{out_path}")

    elif args.copy:
        try:
            import pyperclip
            pyperclip.copy(context)
            if not args.quiet:
                print(f"✅ Context 已複製到剪貼簿（{len(context)} 字元）")
        except ImportError:
            print("⚠️  需要安裝 pyperclip：pip install pyperclip")
            print("    改為輸出到終端：")
            print(context)
    else:
        print(context)


if __name__ == "__main__":
    main()
