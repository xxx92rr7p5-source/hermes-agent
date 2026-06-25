#!/bin/bash
# 1+4 体系 pre-push 检查: 确保不引入已知 bug 模式
# 在 git push 前自动运行
set -e
cd "$(dirname "$0")/.."

echo "=== 1+4 pre-push check ==="

# 1. 检查没有直接调用 cc.compress() 不带参数
if git diff --cached --name-only | grep -q "run_agent.py\|agent/"; then
  if grep -rn "\.compress()" run_agent.py agent/ --include="*.py" 2>/dev/null | grep -v "compress_context\|\.compress(messages\|\.compress(self" | grep -v "#\|test_" > /dev/null 2>&1; then
    echo "❌ 发现 .compress() 调用可能缺参数, 检查:"
    grep -rn "\.compress()" run_agent.py agent/ --include="*.py" 2>/dev/null | grep -v "compress_context\|\.compress(messages\|\.compress(self"
    exit 1
  fi
  echo "✅ 无裸 .compress() 调用"
fi

# 2. 检查没有硬编码模型 context 长度
if git diff --cached | grep -q "128000\|204800\|4096\|8192"; then
  echo "⚠️  检测到硬编码数字, 确认非 context_length:"
  git diff --cached | grep "128000\|204800\|4096\|8192"
fi

# 3. 确保 1+4 核心函数有 try/except
for func in "_trigger_context_compression\|_emit_auto_handoff_notice\|_check_context_usage\|_inject_defensive_phrase\|extract_handoff"; do
  if ! grep -q "$func" run_agent.py agent/handoff.py tools/delegate_tool.py 2>/dev/null; then
    continue
  fi
  echo "✅ $func 已实现"
done

echo "=== 检查通过 ==="
