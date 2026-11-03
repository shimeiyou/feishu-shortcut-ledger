#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "$0")/.." && pwd)"
command -v shortcuts >/dev/null || { echo '需要安装 Apple 快捷指令的 Mac。'; exit 1; }
exec shortcuts sign --mode anyone --input "$task_root/shortcuts/Feishu-Unified-Ledger-Unsigned.shortcut" --output "$task_root/shortcuts/Feishu-Unified-Ledger.signed.shortcut"
