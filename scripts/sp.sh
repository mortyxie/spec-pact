#!/bin/sh
# spec-pact launcher / 启动器。唯一一个"不需要 python 已存在"就能运行的入口。
#
# 阶梯（ladder）：
#   1. $SP_PYTHON 显式指定
#   2. PATH 上的 python3 / python —— 但跳过 agent 托管目录（见 skip 列表）
#   3. py -3（Windows py launcher）
#   4. 常见系统安装目录（不在 PATH 也能找到，这是"agent 又下一份 python"的主因）
#   5. agent 托管运行时（~/.workbuddy 等）—— 只复用，绝不重新下载
#   6. 全失败 → exit 6，打印安装指令，不自动装任何东西
#
# 退出码见 protocol/bootstrap.md：6 = no-python
set -u

# 只用内建命令定位自身：PATH 坏掉时也必须能跑出"没有 python"的结论
case "$0" in
  */*) HERE=${0%/*} ;;
  *)   HERE=. ;;
esac
HERE=$(cd "$HERE" 2>/dev/null && pwd) || HERE=${0%/*}
SCRIPT="$HERE/sp.py"
VCHECK='import sys;sys.exit(0 if sys.version_info[:2]>=(3,8) else 1)'
MIN="3.8"

ok() { "$1" -c "$VCHECK" >/dev/null 2>&1; }
dbg() { if [ "${SP_PACT_DEBUG:-0}" = "1" ]; then echo "sp: $*" >&2; fi; }
low() {
  if command -v tr >/dev/null 2>&1; then printf '%s' "$1" | tr 'A-Z' 'a-z'
  else printf '%s' "$1"; fi
}

if [ ! -f "$SCRIPT" ]; then
  echo "ERR sp: 找不到 $SCRIPT —— launcher 必须与 sp.py 同目录" >&2
  exit 1
fi

# ---- 1. 显式指定 ----
if [ -n "${SP_PYTHON:-}" ]; then
  dbg "SP_PYTHON=$SP_PYTHON"
  if ok "$SP_PYTHON"; then exec "$SP_PYTHON" "$SCRIPT" "$@"; fi
  echo "ERR sp: SP_PYTHON=$SP_PYTHON 不可执行或 < $MIN，继续向下探测" >&2
fi

# ---- 2. PATH ----
agent_py=""
for c in python3 python; do
  p=$(command -v "$c" 2>/dev/null || true)
  [ -n "$p" ] || continue
  case $(low "$p") in
    */.workbuddy/*|*/.cursor/*|*/.claude/*|*/.codex/*|*/pyenv/*|*/uv/*|*/pipx/*|*/npm/*|*/windowsapps/*)
      dbg "skip agent-managed on PATH: $p"
      [ -n "$agent_py" ] || agent_py="$p"
      continue ;;
  esac
  dbg "PATH $p"
  if ok "$p"; then exec "$p" "$SCRIPT" "$@"; fi
done

# ---- 3. Windows py launcher ----
if command -v py >/dev/null 2>&1; then
  if py -3 -c "$VCHECK" >/dev/null 2>&1; then exec py -3 "$SCRIPT" "$@"; fi
fi

# ---- 4. 常见系统安装目录（不在 PATH 也要找到）----
# 设置 SP_PACT_PROBE_DIRS 后「替代」默认探测（自定义安装位置 / 自动化测试用）
if [ -n "${SP_PACT_PROBE_DIRS:-}" ]; then
  probe_dirs=$(printf '%s' "$SP_PACT_PROBE_DIRS" | tr ':;' '  ' 2>/dev/null || printf '%s' "$SP_PACT_PROBE_DIRS")
else
  probe_dirs="/usr/bin /usr/local/bin /opt/homebrew/bin /opt/local/bin /bin"
fi
for d in $probe_dirs; do
  for p in "$d/python3" "$d/python" "$d/python.exe"; do
    [ -f "$p" ] || continue
    dbg "sysdir $p"
    if ok "$p"; then exec "$p" "$SCRIPT" "$@"; fi
  done
done
if [ -z "${SP_PACT_PROBE_DIRS:-}" ]; then
  for p in /c/Python3*/python.exe "/c/Program Files/Python3"*/python.exe \
           /c/ProgramData/Python3*/python.exe \
           "${LOCALAPPDATA:-/nonexistent}"/Programs/Python/Python3*/python.exe; do
    [ -f "$p" ] || continue
    dbg "win-dir $p"
    if ok "$p"; then exec "$p" "$SCRIPT" "$@"; fi
  done
fi

# ---- 5. agent 托管运行时：只复用 ----
if [ -n "$agent_py" ] && ok "$agent_py"; then
  echo "sp: 复用 agent 托管解释器 $agent_py（未下载任何东西）" >&2
  exec "$agent_py" "$SCRIPT" "$@"
fi
for p in "${HOME:-/nonexistent}"/.workbuddy/binaries/python/versions/*/python.exe \
         "${HOME:-/nonexistent}"/.workbuddy/binaries/python/versions/*/bin/python3 \
         "${HOME:-/nonexistent}"/.local/share/uv/python/*/bin/python3 \
         "${HOME:-/nonexistent}"/.pyenv/versions/*/bin/python3; do
  [ -f "$p" ] || continue
  dbg "agent-managed $p"
  if ok "$p"; then
    echo "sp: 复用 agent 托管解释器 $p（未下载任何东西）" >&2
    exec "$p" "$SCRIPT" "$@"
  fi
done

# ---- 6. 全栈失败：不自动安装 ----
{
  echo "ERR sp: no-python —— 本机找不到 >= $MIN 的 python，spec-pact 状态机无法启动。"
  echo "  不会自动下载 python。请任选其一："
  echo ""
  echo "  1) 装一份（一次性，装完登记到用户级 registry）："
  echo "     Windows : winget install -e --id Python.Python.3.12"
  echo "     macOS   : brew install python@3.12"
  echo "     Debian  : sudo apt install python3"
  echo "  2) 已有但不在 PATH："
  echo "     SP_PYTHON=/abs/path/to/python sh scripts/sp.sh <命令>"
  echo "  3) 装不了 / 不想装："
  echo "     进入「手动模式」，见 protocol/bootstrap.md 第 4 节。状态头前缀必须写 degraded，"
  echo "     且不得声称状态经过机器校验。"
  echo ""
  echo "  非标准安装位置可加：SP_PACT_PROBE_DIRS=/dir1:/dir2（替代默认探测）"
} >&2
exit 6
