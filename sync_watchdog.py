#!/usr/bin/env python3
"""
sync_watchdog.py — 事件驅動同步監聽器（含心跳備援）

設計理念：
  取代定時 robocopy/rsync，改用檔案系統監聽。
  NAS 一改，本機立刻知道。

  雙重保險 (Hybrid Approach)：
  - Watchdog 負責 95% 的即時同步
  - 心跳檢測每 5 分鐘確認 NAS 可達，Observer 失效時自動重啟
  - 定時全量同步每小時一次，作為最終備援

安裝依賴：
  pip install watchdog

使用方式：
  python sync_watchdog.py --nas-path Z:\\AI_ControlCenter --local-path C:\\AI_ControlCenter
  python sync_watchdog.py --nas-path /mnt/nas/AI_ControlCenter --local-path ~/AI_ControlCenter
"""

import argparse
import shutil
import sys
import time
import platform
import threading
import logging
from pathlib import Path
from datetime import datetime

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("❌ 需要安裝 watchdog：pip install watchdog")
    sys.exit(1)

# ─────────────────────────────────────────
# 日誌設定
# ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("sync_watchdog.log", encoding="utf-8")
    ]
)
log = logging.getLogger("sync_watchdog")

# ─────────────────────────────────────────
# 設定常數
# ─────────────────────────────────────────
DEBOUNCE_SECONDS = 2.0
HEARTBEAT_INTERVAL = 300      # 5 分鐘
FULL_SYNC_INTERVAL = 3600     # 1 小時
WATCH_EXTENSIONS = {".md", ".json"}
IGNORE_PATTERNS = {".sync", ".hooks", ".node_config.json", "__pycache__", ".git"}


# ─────────────────────────────────────────
# Debounce 事件處理器
# ─────────────────────────────────────────
class DebouncedSyncHandler(FileSystemEventHandler):
    """
    監聽 NAS 上的檔案變動，debounce 後同步到本機。
    同一個檔案在 DEBOUNCE_SECONDS 秒內的多次事件只處理一次。
    """

    def __init__(self, nas_root: Path, local_root: Path):
        super().__init__()
        self.nas_root = nas_root
        self.local_root = local_root
        self._timers = {}
        self._lock = threading.Lock()
        self.sync_count = 0

    def _should_handle(self, path_str: str) -> bool:
        """判斷是否該處理這個事件"""
        path = Path(path_str)

        # 檢查副檔名
        if path.suffix.lower() not in WATCH_EXTENSIONS:
            return False

        # 檢查忽略模式
        parts = path.parts
        for ignore in IGNORE_PATTERNS:
            if ignore in parts:
                return False

        # 忽略暫存檔
        if path.name.startswith(".") or path.name.startswith("~"):
            return False

        return True

    def _debounced_sync(self, src_path: str):
        """Debounce 後的實際同步動作"""
        with self._lock:
            self._timers.pop(src_path, None)

        src = Path(src_path)
        try:
            # 計算相對路徑
            rel = src.relative_to(self.nas_root)
            dest = self.local_root / rel

            # 確保目標目錄存在
            dest.parent.mkdir(parents=True, exist_ok=True)

            # 複製檔案（保留時間戳）
            if src.exists():
                shutil.copy2(src, dest)
                self.sync_count += 1
                log.info(f"🔄 同步：{rel}")
            else:
                log.warning(f"⚠️  來源已不存在：{rel}")

        except Exception as e:
            log.error(f"❌ 同步失敗 {src_path}：{e}")

    def _schedule_sync(self, src_path: str):
        """排程 debounced 同步"""
        if not self._should_handle(src_path):
            return

        with self._lock:
            # 取消之前的計時器（如果有）
            if src_path in self._timers:
                self._timers[src_path].cancel()

            # 設定新的計時器
            timer = threading.Timer(
                DEBOUNCE_SECONDS,
                self._debounced_sync,
                args=[src_path]
            )
            timer.daemon = True
            self._timers[src_path] = timer
            timer.start()

    def on_modified(self, event):
        if not event.is_directory:
            self._schedule_sync(event.src_path)

    def on_created(self, event):
        if not event.is_directory:
            self._schedule_sync(event.src_path)


# ─────────────────────────────────────────
# 全量同步（備援）
# ─────────────────────────────────────────
def full_sync(nas_root: Path, local_root: Path):
    """
    全量單向同步 NAS → 本機。
    只複製「比本機新」的檔案，不刪除本機多餘的檔案。
    """
    synced = 0
    errors = 0

    for src_file in nas_root.rglob("*"):
        if not src_file.is_file():
            continue

        # 檢查副檔名
        if src_file.suffix.lower() not in WATCH_EXTENSIONS:
            continue

        # 檢查忽略
        rel = src_file.relative_to(nas_root)
        parts = rel.parts
        if any(ignore in parts for ignore in IGNORE_PATTERNS):
            continue

        dest_file = local_root / rel

        try:
            # 只複製「比本機新」或「本機不存在」的
            if not dest_file.exists():
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dest_file)
                synced += 1
            elif src_file.stat().st_mtime > dest_file.stat().st_mtime:
                shutil.copy2(src_file, dest_file)
                synced += 1
        except Exception as e:
            log.error(f"❌ 全量同步失敗 {rel}：{e}")
            errors += 1

    log.info(f"📦 全量同步完成：{synced} 檔案更新，{errors} 個錯誤")
    return synced, errors


# ─────────────────────────────────────────
# 心跳檢測
# ─────────────────────────────────────────
class HeartbeatMonitor:
    """
    每 5 分鐘檢查 NAS 是否可達。
    如果不可達，嘗試等待恢復；恢復後重啟 Observer。
    """

    def __init__(self, nas_root: Path, observer: Observer, handler, local_root: Path):
        self.nas_root = nas_root
        self.observer = observer
        self.handler = handler
        self.local_root = local_root
        self._running = True
        self._last_full_sync = time.time()

    def start(self):
        thread = threading.Thread(target=self._loop, daemon=True)
        thread.start()
        return thread

    def stop(self):
        self._running = False

    def _check_nas_alive(self) -> bool:
        """嘗試讀取 NAS 上的 CORE.md 確認可達"""
        try:
            ping_file = self.nas_root / "CORE.md"
            if ping_file.exists():
                # 嘗試實際讀取，確認不是殭屍掛載
                _ = ping_file.read_bytes()[:64]
                return True
            return False
        except (OSError, PermissionError):
            return False

    def _restart_observer(self):
        """重啟 Observer"""
        log.warning("🔄 重啟 Observer...")
        try:
            self.observer.stop()
            self.observer.join(timeout=5)
        except Exception:
            pass

        new_observer = Observer()
        new_observer.schedule(self.handler, str(self.nas_root), recursive=True)
        new_observer.start()
        self.observer = new_observer
        log.info("✅ Observer 已重啟")
        return new_observer

    def _loop(self):
        while self._running:
            time.sleep(HEARTBEAT_INTERVAL)

            if not self._running:
                break

            # 心跳檢測
            if not self._check_nas_alive():
                log.warning("⚠️  NAS 不可達，等待恢復...")
                # 等待 NAS 恢復
                retry_count = 0
                while self._running and not self._check_nas_alive():
                    retry_count += 1
                    if retry_count % 6 == 0:  # 每 30 秒報告一次
                        log.warning(f"⚠️  NAS 仍不可達（已等待 {retry_count * 5} 秒）")
                    time.sleep(5)

                if self._running:
                    log.info("✅ NAS 恢復連線")
                    self.observer = self._restart_observer()
                    # 恢復後做一次全量同步
                    full_sync(self.nas_root, self.local_root)
            else:
                log.debug("💚 NAS 心跳正常")

            # 定時全量同步
            now = time.time()
            if now - self._last_full_sync >= FULL_SYNC_INTERVAL:
                log.info("⏰ 執行定時全量同步")
                full_sync(self.nas_root, self.local_root)
                self._last_full_sync = now


# ─────────────────────────────────────────
# 主程式
# ─────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="AI 協作框架 — 事件驅動同步監聽器"
    )
    parser.add_argument("--nas-path", required=True, help="NAS 中央架構路徑")
    parser.add_argument("--local-path", required=True, help="本機讀取點路徑")
    parser.add_argument("--full-sync-only", action="store_true",
                        help="只執行一次全量同步，不啟動監聽")
    args = parser.parse_args()

    nas_root = Path(args.nas_path)
    local_root = Path(args.local_path)

    if not nas_root.exists():
        print(f"❌ NAS 路徑不存在：{nas_root}")
        sys.exit(1)

    local_root.mkdir(parents=True, exist_ok=True)

    # 僅全量同步模式
    if args.full_sync_only:
        full_sync(nas_root, local_root)
        return

    # 首次全量同步
    log.info(f"📦 首次全量同步：{nas_root} → {local_root}")
    full_sync(nas_root, local_root)

    # 啟動 Watchdog
    handler = DebouncedSyncHandler(nas_root, local_root)
    observer = Observer()
    observer.schedule(handler, str(nas_root), recursive=True)
    observer.start()
    log.info(f"👁️  監聽啟動：{nas_root}")

    # 啟動心跳監測
    heartbeat = HeartbeatMonitor(nas_root, observer, handler, local_root)
    heartbeat.start()
    log.info(f"💚 心跳監測啟動（每 {HEARTBEAT_INTERVAL} 秒）")
    log.info(f"⏰ 全量備援同步（每 {FULL_SYNC_INTERVAL} 秒）")

    print(f"\n{'═'*50}")
    print(f"  同步監聽器運行中")
    print(f"  NAS：{nas_root}")
    print(f"  本機：{local_root}")
    print(f"  按 Ctrl+C 停止")
    print(f"{'═'*50}\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("⏹️  收到停止信號")
        heartbeat.stop()
        observer.stop()
        observer.join()
        log.info(f"📊 本次同步統計：{handler.sync_count} 個檔案")
        print("\n✅ 已安全停止")


if __name__ == "__main__":
    main()
