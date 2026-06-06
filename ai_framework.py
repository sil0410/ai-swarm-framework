#!/usr/bin/env python3
"""
ai_framework.py — AI Swarm Framework跨平台啟動器

目標：
- 四台不同平台只記一個入口：python ai_framework.py ...
- 安裝時只要貼上/選擇 NAS 路徑、本機路徑、agent 身份。
- 日常用 start/status/context/task/handoff，不用記多支腳本。

不做的事：
- 不自動刪除 NAS 資料。
- 不自動改 CORE.md / AGENTS.md。
- 不自動對外發布。
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

APP = "AI Swarm Framework v0.1.0"
ROOT = Path(__file__).resolve().parent
CONFIG_NAME = ".node_config.json"
AGENTS = ["Coordinator", "Planner", "Producer", "Researcher"]

SAFE_COPY_SKIP_DIRS = {".sync", ".hooks", "__pycache__", ".git"}
SWARM_DIRS = [
    "swarm/tasks/inbox",
    "swarm/tasks/active",
    "swarm/tasks/blocked",
    "swarm/tasks/done",
    "swarm/handoffs/pending",
    "swarm/handoffs/accepted",
    "swarm/handoffs/done",
    "swarm/status",
    "swarm/outputs",
    "swarm/templates",
]


def c(text: str) -> str:
    return text


def info(msg: str) -> None:
    print(f"ℹ {msg}")


def ok(msg: str) -> None:
    print(f"✅ {msg}")


def warn(msg: str) -> None:
    print(f"⚠ {msg}")


def fail(msg: str, code: int = 1) -> None:
    print(f"❌ {msg}", file=sys.stderr)
    sys.exit(code)


def detect_os() -> str:
    name = platform.system().lower()
    if name == "darwin":
        return "macos"
    if name == "windows":
        return "windows"
    return "linux"


def default_local_path() -> Path:
    if detect_os() == "windows":
        return Path("C:/AI_ControlCenter")
    return Path.home() / "AI_ControlCenter"


def ask(prompt: str, default: str | None = None, required: bool = True) -> str:
    hint = f" [{default}]" if default else ""
    while True:
        value = input(f"{prompt}{hint}: ").strip().strip('"')
        if not value and default is not None:
            return default
        if value or not required:
            return value
        warn("此欄位必填")


def choose_folder(default: str | None = None) -> str | None:
    """Optional GUI folder picker. Falls back silently when Tk is unavailable."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        selected = filedialog.askdirectory(initialdir=default or str(Path.home()))
        root.destroy()
        return selected or None
    except Exception:
        return None


def normalize_path(value: str) -> Path:
    # pathlib on Windows accepts both C:/... and //server/share/...
    return Path(value).expanduser()


def load_node_config(required: bool = True) -> dict | None:
    candidates = [ROOT / CONFIG_NAME]
    for p in candidates:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    if required:
        fail(f"尚未安裝節點設定。請先執行：python ai_framework.py install")
    return None


def write_node_config(cfg: dict) -> None:
    (ROOT / CONFIG_NAME).write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    local = Path(cfg["local_path"])
    local.mkdir(parents=True, exist_ok=True)
    (local / CONFIG_NAME).write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ensure_swarm(root: Path) -> None:
    for rel in SWARM_DIRS:
        (root / rel).mkdir(parents=True, exist_ok=True)

    task_template = root / "swarm/templates/task.json"
    if not task_template.exists():
        task_template.write_text(json.dumps({
            "id": "TASK-YYYYMMDD-001",
            "title": "Short task title",
            "project": "project-name",
            "assignee": "Planner",
            "status": "active",
            "created_by": "Human",
            "created_at": "YYYY-MM-DDTHH:MM:SS",
            "depends_on": [],
            "next_agents": [],
            "goal": "What success means",
            "acceptance_criteria": [],
            "files": [],
            "risk": "low",
            "human_review_required": False,
            "notes": ""
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    handoff_template = root / "swarm/templates/handoff.json"
    if not handoff_template.exists():
        handoff_template.write_text(json.dumps({
            "id": "HANDOFF-YYYYMMDD-001",
            "from": "Planner",
            "to": "Producer",
            "parent_task": "TASK-YYYYMMDD-001",
            "status": "pending",
            "created_at": "YYYY-MM-DDTHH:MM:SS",
            "summary": "What was completed",
            "next_action": "What the receiving agent must do next",
            "files": [],
            "acceptance_criteria": [],
            "decision_needed": None,
            "risk": "low",
            "human_review_required": False,
            "notes": ""
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ensure_governance_templates(root: Path) -> None:
    """Create starter governance files only when they do not already exist."""
    template_map = {
        "CORE.md": ROOT / "templates" / "CORE.md",
        "AGENTS.md": ROOT / "templates" / "AGENTS.md",
        "projects/demo.md": ROOT / "templates" / "project.md",
        "skills/example_skill.md": ROOT / "templates" / "skill.md",
    }
    for rel, template in template_map.items():
        target = root / rel
        if target.exists() or not template.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template, target)


def safe_sync(nas_root: Path, local_root: Path) -> int:
    if not nas_root.exists():
        fail(f"NAS 路徑不存在或尚未掛載：{nas_root}")
    local_root.mkdir(parents=True, exist_ok=True)
    synced = 0
    for src in nas_root.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(nas_root)
        if any(part in SAFE_COPY_SKIP_DIRS for part in rel.parts):
            continue
        dest = local_root / rel
        if not dest.exists() or src.stat().st_mtime > dest.stat().st_mtime:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            synced += 1
    return synced


def run_py(script: str, args: list[str], check: bool = True) -> int:
    cmd = [sys.executable, str(ROOT / script)] + args
    return subprocess.run(cmd, cwd=str(ROOT), check=check).returncode


def cmd_install(args) -> None:
    print(f"\n{APP} 安裝精靈")
    print("=" * 50)
    print("這台機器只需要設定三件事：NAS 路徑、本機讀取點、Agent 身份。")
    print("NAS 路徑可以是 Windows UNC、macOS 掛載路徑或 Linux 掛載路徑。")
    print()

    selected = None
    if args.pick:
        selected = choose_folder(args.nas_path)
        if selected:
            ok(f"已選擇 NAS 路徑：{selected}")
        else:
            warn("無法開啟資料夾選擇器，改用貼上路徑。")

    nas_text = args.nas_path or selected or ask(
        "請貼上這台電腦連到 NAS 的 AI_ControlCenter 路徑",
        default="//server/share/AI_ControlCenter" if detect_os() == "windows" else None,
    )
    nas_root = normalize_path(nas_text)

    local_text = args.local_path or ask("本機讀取點", default=str(default_local_path()))
    local_root = normalize_path(local_text)

    agent = args.agent
    if not agent:
        print("\n這台是哪個 Agent？")
        for i, name in enumerate(AGENTS, 1):
            print(f"  {i}. {name}")
        while True:
            choice = ask("請輸入編號或名稱", default="1")
            if choice.isdigit() and 1 <= int(choice) <= len(AGENTS):
                agent = AGENTS[int(choice) - 1]
                break
            matches = [a for a in AGENTS if a.lower() == choice.lower()]
            if matches:
                agent = matches[0]
                break
            warn("請輸入有效 agent：Coordinator / Planner / Producer / Researcher")

    if not nas_root.exists():
        fail(f"NAS 路徑不存在：{nas_root}\n請先在作業系統掛載 NAS，或確認貼上的路徑正確。")

    ensure_swarm(nas_root)
    ensure_governance_templates(nas_root)
    synced = safe_sync(nas_root, local_root)
    ensure_swarm(local_root)
    ensure_governance_templates(local_root)

    cfg = {
        "agent": agent,
        "nas_path": str(nas_root),
        "local_path": str(local_root),
        "os": detect_os(),
        "installed_at": datetime.now().isoformat(timespec="seconds"),
        "framework_root": str(ROOT),
    }
    write_node_config(cfg)

    ok(f"節點安裝完成：{agent}")
    ok(f"本機讀取點：{local_root}")
    ok(f"NAS 路徑：{nas_root}")
    ok(f"首次同步：{synced} 個檔案")
    print("\n下一步：")
    print("  1. 檢查狀態：python ai_framework.py status")
    print("  2. 產生 context：python ai_framework.py context --project demo")
    print("  3. 啟動同步：python ai_framework.py start")


def cmd_status(args) -> None:
    cfg = load_node_config()
    nas_root = Path(cfg["nas_path"])
    local_root = Path(cfg["local_path"])
    print(f"# {APP} 節點狀態")
    print(f"Agent: {cfg['agent']}")
    print(f"OS: {cfg['os']}")
    print(f"NAS: {nas_root} ({'OK' if nas_root.exists() else 'MISSING'})")
    print(f"Local: {local_root} ({'OK' if local_root.exists() else 'MISSING'})")
    print()
    if local_root.exists():
        cmd = ["--path", str(local_root), "--agent", cfg["agent"]]
        if args.all:
            cmd.append("--all")
        run_py("swarm_check.py", cmd, check=False)


def cmd_start(args) -> None:
    cfg = load_node_config()
    nas_root = Path(cfg["nas_path"])
    local_root = Path(cfg["local_path"])
    ensure_swarm(nas_root)
    ensure_swarm(local_root)
    print("啟動同步監聽。此視窗請保持開啟；停止請按 Ctrl+C。")
    run_py("sync_watchdog.py", ["--nas-path", str(nas_root), "--local-path", str(local_root)], check=False)


def cmd_sync(args) -> None:
    cfg = load_node_config()
    synced = safe_sync(Path(cfg["nas_path"]), Path(cfg["local_path"]))
    ensure_swarm(Path(cfg["local_path"]))
    ok(f"同步完成：{synced} 個檔案")


def cmd_context(args) -> None:
    cfg = load_node_config()
    local_root = Path(cfg["local_path"])
    project = args.project or ask("專案名稱", default="demo")
    agent = args.agent or cfg["agent"]
    cmd = ["--path", str(local_root), "--project", project, "--agent", agent]
    if args.copy:
        cmd.append("--copy")
    if args.out:
        cmd += ["--out", args.out]
    run_py("inject_v2.py", cmd, check=False)


def cmd_task(args) -> None:
    cfg = load_node_config()
    path = str(Path(cfg["nas_path"]) if args.central else Path(cfg["local_path"]))
    cmd = ["--path", path, "--project", args.project, "--title", args.title, "--assignee", args.assignee, "--goal", args.goal]
    for value in args.next_agent or []:
        cmd += ["--next-agent", value]
    for value in args.acceptance or []:
        cmd += ["--acceptance", value]
    if args.review:
        cmd.append("--human-review-required")
    run_py("swarm_create_task.py", cmd, check=False)


def cmd_handoff(args) -> None:
    cfg = load_node_config()
    path = str(Path(cfg["nas_path"]) if args.central else Path(cfg["local_path"]))
    cmd = [
        "--path", path,
        "--from-agent", args.from_agent or cfg["agent"],
        "--to-agent", args.to_agent,
        "--task", args.task,
        "--summary", args.summary,
        "--next-action", args.next_action,
    ]
    for value in args.file or []:
        cmd += ["--file", value]
    for value in args.acceptance or []:
        cmd += ["--acceptance", value]
    if args.review:
        cmd.append("--human-review-required")
    run_py("swarm_create_handoff.py", cmd, check=False)


def cmd_agent_prompt(args) -> None:
    cfg = load_node_config()
    agent = args.agent or cfg["agent"]
    project = args.project or "demo"
    print(f"""你是 {agent}，AI Swarm Framework中的一員。

請先讀取這台機器產生的 context，並依照 CORE.md / AGENTS.md 啟動。
啟動後先用三行內確認：
1. 你是誰
2. team/project goal
3. 最高強限制

接著檢查 swarm tasks / handoffs，回報你目前應該做什麼。

若需要產生 context，請在此電腦執行：
python ai_framework.py context --project {project} --agent {agent} --copy
""")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI Swarm Framework跨平台啟動器")
    sub = parser.add_subparsers(dest="command", required=True)

    p_install = sub.add_parser("install", help="設定這台機器：NAS 路徑、本機路徑、agent 身份")
    p_install.add_argument("--nas-path", help="這台電腦連到 NAS 的 AI_ControlCenter 路徑")
    p_install.add_argument("--local-path", help="本機讀取點")
    p_install.add_argument("--agent", choices=AGENTS, help="Coordinator / Planner / Producer / Researcher")
    p_install.add_argument("--pick", action="store_true", help="嘗試開啟資料夾選擇器")
    p_install.set_defaults(func=cmd_install)

    p_status = sub.add_parser("status", help="檢查本機節點與 swarm 狀態")
    p_status.add_argument("--all", action="store_true", help="顯示全局 swarm 狀態")
    p_status.set_defaults(func=cmd_status)

    p_start = sub.add_parser("start", help="啟動 NAS → 本機同步監聽")
    p_start.set_defaults(func=cmd_start)

    p_sync = sub.add_parser("sync", help="手動同步一次 NAS → 本機")
    p_sync.set_defaults(func=cmd_sync)

    p_context = sub.add_parser("context", help="產生目前 agent 的工作 context")
    p_context.add_argument("--project", help="專案名稱，例如 demo")
    p_context.add_argument("--agent", choices=AGENTS, help="指定 agent，預設用本機身份")
    p_context.add_argument("--copy", action="store_true", help="複製到剪貼簿")
    p_context.add_argument("--out", help="輸出成檔案")
    p_context.set_defaults(func=cmd_context)

    p_task = sub.add_parser("task", help="建立任務")
    p_task.add_argument("--project", required=True)
    p_task.add_argument("--title", required=True)
    p_task.add_argument("--assignee", required=True, choices=AGENTS)
    p_task.add_argument("--goal", required=True)
    p_task.add_argument("--next-agent", action="append", choices=AGENTS)
    p_task.add_argument("--acceptance", action="append")
    p_task.add_argument("--review", action="store_true", help="需要 human 審核")
    p_task.add_argument("--central", action="store_true", help="直接寫 NAS；預設寫本機讀取點")
    p_task.set_defaults(func=cmd_task)

    p_handoff = sub.add_parser("handoff", help="建立 agent 交付")
    p_handoff.add_argument("--from-agent", choices=AGENTS, help="來源 agent，預設本機身份")
    p_handoff.add_argument("--to-agent", required=True, choices=AGENTS)
    p_handoff.add_argument("--task", required=True)
    p_handoff.add_argument("--summary", required=True)
    p_handoff.add_argument("--next-action", required=True)
    p_handoff.add_argument("--file", action="append")
    p_handoff.add_argument("--acceptance", action="append")
    p_handoff.add_argument("--review", action="store_true", help="需要 human 審核")
    p_handoff.add_argument("--central", action="store_true", help="直接寫 NAS；預設寫本機讀取點")
    p_handoff.set_defaults(func=cmd_handoff)

    p_prompt = sub.add_parser("agent-prompt", help="輸出貼給 Hermes/Claude 的啟動提示")
    p_prompt.add_argument("--project")
    p_prompt.add_argument("--agent", choices=AGENTS)
    p_prompt.set_defaults(func=cmd_agent_prompt)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
