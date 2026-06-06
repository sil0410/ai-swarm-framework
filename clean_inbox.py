#!/usr/bin/env python3
"""
clean_inbox.py — Inbox 歸檔工具

設計理念：
  Inbox 是「收發室」，不是「檔案庫」。
  Human 審核完 inbox 後，手動執行此腳本，
  把超過指定天數的檔案搬到 archive/。

  不自動執行、不刪除、不覆蓋。

使用方式：
  python clean_inbox.py --path Z:\\AI_ControlCenter
  python clean_inbox.py --path Z:\\AI_ControlCenter --days 7
  python clean_inbox.py --path Z:\\AI_ControlCenter --dry-run
"""

import argparse
import shutil
import sys
from pathlib import Path
from datetime import datetime, timedelta


def archive_inbox(
    root: Path,
    days: int = 3,
    dry_run: bool = False
) -> tuple:
    """
    將 inbox/ 中超過指定天數的 .md 檔案搬到 archive/{年份}/{月份}/。

    回傳 (moved_count, skipped_count)
    """
    inbox = root / "inbox"
    if not inbox.exists():
        print("📭 inbox/ 不存在，無需清理")
        return 0, 0

    cutoff = datetime.now() - timedelta(days=days)
    moved = 0
    skipped = 0
    errors = 0

    files = sorted(inbox.glob("*.md"))
    if not files:
        print("📭 inbox/ 為空，無需清理")
        return 0, 0

    print(f"🔍 掃描 inbox/（{len(files)} 個檔案，閾值 {days} 天）")

    for f in files:
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        age = datetime.now() - mtime

        if mtime < cutoff:
            # 建立歸檔目錄
            year_month = mtime.strftime("%Y/%m")
            archive_dir = root / "archive" / year_month
            dest = archive_dir / f.name

            if dry_run:
                print(f"  [DRY RUN] 會搬移：{f.name} → archive/{year_month}/")
                moved += 1
            else:
                try:
                    archive_dir.mkdir(parents=True, exist_ok=True)

                    # 防止覆蓋（不太可能但以防萬一）
                    if dest.exists():
                        stem = f.stem
                        suffix = f.suffix
                        counter = 1
                        while dest.exists():
                            dest = archive_dir / f"{stem}_{counter}{suffix}"
                            counter += 1

                    shutil.move(str(f), str(dest))
                    print(f"  📦 {f.name} → archive/{year_month}/")
                    moved += 1
                except Exception as e:
                    print(f"  ❌ 搬移失敗 {f.name}：{e}")
                    errors += 1
        else:
            skipped += 1

    # 摘要
    print(f"\n{'─'*40}")
    if dry_run:
        print(f"  [DRY RUN] 預計搬移 {moved} 個，保留 {skipped} 個")
    else:
        print(f"  ✅ 已歸檔 {moved} 個，保留 {skipped} 個"
              + (f"，{errors} 個失敗" if errors else ""))

    return moved, skipped


def show_inbox_summary(root: Path):
    """顯示 inbox 現況摘要"""
    inbox = root / "inbox"
    if not inbox.exists():
        print("📭 inbox/ 不存在")
        return

    files = sorted(inbox.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        print("📭 inbox/ 為空")
        return

    # 按 agent 分組
    by_agent = {}
    by_project = {}
    for f in files:
        parts = f.stem.split("_")
        if len(parts) >= 4:
            project = parts[0]
            agent = parts[-1]
            by_agent.setdefault(agent, []).append(f)
            by_project.setdefault(project, []).append(f)

    print(f"\n📬 Inbox 摘要（{len(files)} 個檔案）")
    print(f"{'─'*40}")

    if by_agent:
        print("\n  按 Agent：")
        for agent, agent_files in sorted(by_agent.items()):
            print(f"    {agent}：{len(agent_files)} 個")

    if by_project:
        print("\n  按專案：")
        for project, proj_files in sorted(by_project.items()):
            print(f"    {project}：{len(proj_files)} 個")

    # 最舊的檔案
    oldest = files[-1]
    oldest_age = datetime.now() - datetime.fromtimestamp(oldest.stat().st_mtime)
    print(f"\n  最舊：{oldest.name}（{oldest_age.days} 天前）")
    print(f"  最新：{files[0].name}")


def main():
    parser = argparse.ArgumentParser(
        description="AI 協作框架 — Inbox 歸檔工具"
    )
    parser.add_argument("--path", required=True, help="架構根目錄路徑")
    parser.add_argument("--days", type=int, default=3,
                        help="超過幾天的檔案要歸檔（預設 3）")
    parser.add_argument("--dry-run", action="store_true",
                        help="只顯示會做什麼，不實際搬移")
    parser.add_argument("--summary", action="store_true",
                        help="只顯示 inbox 摘要，不歸檔")
    args = parser.parse_args()

    root = Path(args.path)
    if not root.exists():
        print(f"❌ 路徑不存在：{root}")
        sys.exit(1)

    if args.summary:
        show_inbox_summary(root)
    else:
        archive_inbox(root, args.days, args.dry_run)


if __name__ == "__main__":
    main()
