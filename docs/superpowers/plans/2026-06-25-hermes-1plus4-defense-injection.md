# 1+4 体系防御注入 v1.0 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 hermes-agent 代码库中实现 1+4 体系的 5 大防御 capability：派单模板注入、context 滚动、handoff 压缩、配置漂移监控、skill 字段同步。

**Architecture:** 在现有 `tools/delegate_tool.py`（派单）和 `run_agent.py`（agent 运行时）上叠加防御层，新建 `agent/handoff.py`（handoff 提取），不替代任何现有机制。所有防御均为注入/监控层，核心调度逻辑不变。

**Tech Stack:** Python 3.x (hermes-agent), Bash (config drift), Markdown (skill sync)

**Base Ref:** `bede8fc4993b5c1ee680ee818f229f0c4e5b2684`

**Spec:** `docs/superpowers/specs/2026-06-25-hermes-1plus4-defense-injection-design.md`

---

## 前置任务：处理脏工作树

### Task 0: Clean Working Tree

**当前状态**: 16 个未提交文件（含目标文件 `hermes_cli/main.py`）

- [ ] **Step 0.1: 检查现有改动是否与本次任务冲突**

```bash
cd E:\.hermes\hermes-agent
git diff --name-only
```

- [ ] **Step 0.2: 如冲突，stash 现有改动**

```bash
git stash push -m "pre-1plus4-defense: preserve existing work"
```

- [ ] **Step 0.3: 如不冲突，确认后继续**

```bash
git status
```

---

## File Structure

| 文件 | 操作 | 职责 |
|------|------|------|
| `tools/delegate_tool.py` | 修改 | 加 `_inject_defensive_phrase()` + 调用点 |
| `run_agent.py` | 修改 | `AIAgent` 加 `_check_context_usage()` |
| `agent/handoff.py` | **新建** | `extract_handoff()` + `Handoff` dataclass |
| `tests/agent/test_handoff.py` | **新建** | 5 case 单测 |
| `~/.hermes/bin/config-drift-check.sh` | **新建** (仓库外) | Config drift 监控脚本 |
| `~/.hermes/bin/update-config-baseline.sh` | **新建** (仓库外) | 手动更新 baseline |
| `skills/agent-workflow/task-persistence/SKILL.md` | 修改 | v1.0 字段同步 |

---

### Task 1: `defensive-dispatch` — 派单模板注入

**Files:**
- Modify: `tools/delegate_tool.py` (加函数 + 2 处调用)

- [ ] **Step 1.1: 读取现有代码确认注入点**

```bash
grep -n "def _build_child_system_prompt\|def delegate_task\|_inject_defensive" tools/delegate_tool.py
```

确认 `_build_child_system_prompt` 在 665 行，`delegate_task` 在 2074 行，无现有 `_inject_defensive_phrase`。

- [ ] **Step 1.2: 在 `delegate_tool.py` 顶部（`_load_config()` 之后）添加模板和注入函数**

位置：约第 960 行（`_build_child_system_prompt` 之前，`_load_config` 相关代码之后）

```python
# ==== 1+4 体系防御注入: 5 防御话 8 字段模板 ====

_DEFENSIVE_TEMPLATE = """[Task]: {goal}

ACCEPTANCE: (≥6 项可验证 checklist — 由派单者填写)
WORKSPACE: {workspace}
TIMEOUT: {timeout}s
DEPENDENCIES: parents=[]
NO FABRICATION: 没做就说没做, cite file:line, 不编 PR / id
INSTALL_POLICY: {install_policy}
FORBIDDEN_FILES: {forbidden_files}
VISION_REQUIRED: {vision_required}"""


def _inject_defensive_phrase(goal: str, overrides: dict = None) -> str:
    """注入 5 防御话 8 字段模板到 goal 开头。

    幂等: 如果 goal 已以 '[Task]:' 开头则跳过注入。
    默认值从 delegation.defensive_phrase config 读取。
    overrides 字典允许逐字段覆盖默认值。

    Returns:
        注入 8 字段后的完整 goal 字符串
    """
    goal_stripped = goal.strip() if goal else ""
    if goal_stripped.startswith('[Task]:'):
        return goal  # 已注入, 幂等跳过

    cfg = _load_config()
    defense = cfg.get('defensive_phrase', {})

    params = {
        'goal': goal_stripped,
        'workspace': os.getenv('TERMINAL_CWD', ''),
        'timeout': defense.get('timeout', 1800),
        'install_policy': defense.get('install_policy', 'pnpm-lock'),
        'forbidden_files': ', '.join(defense.get('forbidden_files', [
            'hermes_state.py',
            'hermes_constants.py',
            'hermes_logging.py',
        ])),
        'vision_required': str(defense.get('vision_required', False)).lower(),
    }
    if overrides:
        params.update(overrides)

    return _DEFENSIVE_TEMPLATE.format(**params)
```

- [ ] **Step 1.3: 在 `delegate_task()` 的单任务路径调用注入**

找到约 2183-2186 行：
```python
# 原来:
    elif goal and isinstance(goal, str) and goal.strip():
        task_list = [
            {"goal": goal, "context": context, "toolsets": toolsets, "role": top_role}
        ]

# 改为:
    elif goal and isinstance(goal, str) and goal.strip():
        injected_goal = _inject_defensive_phrase(goal)
        task_list = [
            {"goal": injected_goal, "context": context, "toolsets": toolsets, "role": top_role}
        ]
```

- [ ] **Step 1.4: 在 `delegate_task()` 的批量任务路径调用注入**

找到约 2173-2181 行，对 `tasks` 列表中的每个 task goal 注入：
```python
# 在 task_list = tasks 之前加:
        for t in tasks:
            if isinstance(t, dict) and 'goal' in t:
                t['goal'] = _inject_defensive_phrase(t['goal'])
```

- [ ] **Step 1.5: 运行测试确认无回归**

```bash
cd E:\.hermes\hermes-agent
scripts/run_tests.sh -v --tb=short
```

期望: 全过, 0 fail

- [ ] **Step 1.6: CLI smoke test**

```bash
hermes --version
hermes -p default chat "ping"
```

期望: 正常响应

- [ ] **Step 1.7: Commit (流云手动)**

```bash
git add tools/delegate_tool.py
git commit -m "refactor(1+4): 派单模板自动注入 5 防御话 8 字段

引用 22 号 §四
8 字段: ACCEPTANCE / WORKSPACE / TIMEOUT / DEPENDENCIES / NO FABRICATION
+ INSTALL_POLICY=pnpm-lock / FORBIDDEN_FILES / VISION_REQUIRED=false
注入点: tools/delegate_tool.py _inject_defensive_phrase()
幂等: 已含 [Task]: 前缀则跳过"
```

---

### Task 2: `context-rolling` — Context 滚动 50/70/80%

**Files:**
- Modify: `run_agent.py` (AIAgent 类)

- [ ] **Step 2.1: 读取 AIAgent 现有 context 相关代码**

```bash
grep -n "context_compressor\|context_usage\|_check_compression\|max_tokens" run_agent.py | head -30
```

- [ ] **Step 2.2: 在 `AIAgent.__init__()` 加 context 监控属性**

找到 `__init__` 方法（约 356 行），在属性赋值区域加：
```python
        # 1+4 体系: context 滚动监控
        self._context_usage_percent = 0
        self._model_max_context = 128000  # fallback, 实际从 model_metadata 读取
```

- [ ] **Step 2.3: 在 `run_agent.py` 模块级添加辅助函数**

```python
def _get_model_max_context(agent) -> int:
    """从 model_metadata 读取当前模型的最大 context 长度。"""
    try:
        from agent.model_metadata import get_model_metadata
        model = getattr(agent, 'model', '')
        if model:
            meta = get_model_metadata(model)
            if meta and 'max_context' in meta:
                return meta['max_context']
    except Exception:
        pass
    return getattr(agent, '_model_max_context', 128000)
```

- [ ] **Step 2.4: 添加 `AIAgent._check_context_usage()` 方法**

```python
    def _check_context_usage(self, response) -> None:
        """50/70/80% 三级 context 占用监控 (1+4 体系 25 号 §四)。

        50% → info 日志 (P-F15 软信号)
        70% → warning 日志 (压缩候选)
        80% → 自动触发现有 context_compressor
        """
        if not (hasattr(response, 'usage') and response.usage):
            return

        input_tokens = response.usage.input_tokens
        max_ctx = _get_model_max_context(self)
        if max_ctx <= 0:
            return

        pct = int(input_tokens / max_ctx * 100)
        self._context_usage_percent = pct

        if pct >= 80:
            logger.warning(
                "1+4 context usage at %d%%, triggering forced compression", pct
            )
            cc = getattr(self, 'context_compressor', None)
            if cc is not None:
                try:
                    self._trigger_context_compression()
                except Exception as exc:
                    logger.error(
                        "1+4 context compression failed at %d%%: %s", pct, exc
                    )
        elif pct >= 70:
            logger.warning(
                "1+4 context usage at %d%%, compress candidate", pct
            )
        elif pct >= 50:
            logger.info("1+4 context usage at %d%%", pct)

    def _trigger_context_compression(self) -> None:
        """触发 context_compressor 压缩 (1+4 体系 80% 强制压缩)。"""
        from agent.context_compressor import ContextCompressor
        cc = getattr(self, 'context_compressor', None)
        if isinstance(cc, ContextCompressor):
            cc.compress()
```

- [ ] **Step 2.5: 在主 API 调用循环中调用 `_check_context_usage`**

找到 `chat.completions.create` 调用后的 response 处理点。在 `agent/agent_runtime_helpers.py` 或 `run_agent.py` 中找到 API 调用返回位置，加：
```python
        # 1+4 体系: 每次 API 调用后检查 context 占用
        self._check_context_usage(response)
```

- [ ] **Step 2.6: 运行 agent 相关测试**

```bash
cd E:\.hermes\hermes-agent
scripts/run_tests.sh tests/agent/test_run_agent.py -v --tb=long
```

期望: 全过, 0 fail

- [ ] **Step 2.7: Commit (流云手动)**

```bash
git add run_agent.py
git commit -m "refactor(1+4): context 滚动 50/70/80% 自动 trigger

引用 25 号 §四 4 早期信号
P-F15 防御: 50% info / 70% warning / 80% 强制压缩
叠加现有 context_compressor, 不替代"
```

---

### Task 3: `handoff-compression` — D1+D2 Handoff 提取

**Files:**
- Create: `agent/handoff.py`
- Modify: `tools/delegate_tool.py` (`_run_single_child`)
- Create: `tests/agent/test_handoff.py`

- [ ] **Step 3.1: 新建 `agent/handoff.py`**

```python
"""1+4 体系 D1+D2 Handoff 强制压缩.

从子 agent 的 stdout 提取结构化 handoff dict,
父 context 只收 handoff 摘要, 不收 raw stdout。
"""

import re
from dataclasses import dataclass, field, asdict
from typing import List


@dataclass
class Handoff:
    """子 agent 返回的 handoff 数据结构 (1+4 体系 8 段交接)。"""
    changed_files: List[str] = field(default_factory=list)
    tests_run: List[str] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    next_step: str = ""
    blocking_issues: List[str] = field(default_factory=list)


# 中英双语正则模式
_BULLET_PATTERNS = {
    'changed_files': [
        r'(?:files?\s*(?:created|modified|changed))\s*:\s*\n((?:\s*[-*]\s*.+\n?)+)',
        r'(?:创建|修改|更改)(?:了)?(?:文件)?\s*:\s*\n((?:\s*[-*]\s*.+\n?)+)',
    ],
    'tests_run': [
        r'(?:tests?\s*(?:run|executed|passed|failed))\s*:\s*\n((?:\s*[-*]\s*.+\n?)+)',
        r'(?:测试|运行)(?:了)?\s*:\s*\n((?:\s*[-*]\s*.+\n?)+)',
    ],
    'decisions': [
        r'(?:decisions?|key\s*decisions?)\s*:\s*\n((?:\s*[-*]\s*.+\n?)+)',
        r'(?:关键)?(?:决策|决定)\s*:\s*\n((?:\s*[-*]\s*.+\n?)+)',
    ],
    'blocking_issues': [
        r'(?:blocking\s*issues?|issues?\s*encountered)\s*:\s*\n((?:\s*[-*]\s*.+\n?)+)',
        r'(?:问题|阻塞)\s*:\s*\n((?:\s*[-*]\s*.+\n?)+)',
    ],
}

_NEXT_STEP_PATTERNS = [
    r'(?:next\s*steps?|下一步)\s*:\s*(.+?)(?:\n\n|\n\*|\n-|\n[A-Z]|\Z)',
]


def _extract_bullet_list(text: str, patterns: list) -> list:
    """从文本提取 bullet list。"""
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
        if match:
            items = re.findall(r'[-*]\s*(.+)', match.group(1))
            return [item.strip() for item in items if item.strip()]
    return []


def _extract_single_line(text: str, patterns: list) -> str:
    """从文本提取单行值。"""
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
    return ""


def extract_handoff(stdout) -> dict:
    """从子 agent stdout 提取结构化 handoff dict。

    Args:
        stdout: 子 agent 完整输出文本 (str) 或 None/非字符串

    Returns:
        dict: Handoff 结构 (可 JSON 序列化), 异常或空输入返回空结构
    """
    if not stdout or not isinstance(stdout, str):
        return asdict(Handoff())

    try:
        handoff = Handoff(
            changed_files=_extract_bullet_list(stdout, _BULLET_PATTERNS['changed_files']),
            tests_run=_extract_bullet_list(stdout, _BULLET_PATTERNS['tests_run']),
            decisions=_extract_bullet_list(stdout, _BULLET_PATTERNS['decisions']),
            next_step=_extract_single_line(stdout, _NEXT_STEP_PATTERNS),
            blocking_issues=_extract_bullet_list(stdout, _BULLET_PATTERNS['blocking_issues']),
        )
        return asdict(handoff)
    except Exception:
        return asdict(Handoff())
```

- [ ] **Step 3.2: 新建 `tests/agent/test_handoff.py` (5 case)**

```python
"""1+4 体系 handoff 单测 — extract_handoff 5 case。"""
import pytest
from agent.handoff import extract_handoff, Handoff


class TestExtractHandoff:
    """extract_handoff 5 用例。"""

    def test_case1_changed_files_and_tests(self):
        """Case 1: stdout 含 changed_files + tests_run。"""
        stdout = (
            "Files changed:\n"
            "- src/a.py\n"
            "- src/b.py\n"
            "\n"
            "Tests run:\n"
            "- test_x passed\n"
            "- test_y passed\n"
        )
        result = extract_handoff(stdout)
        assert result['changed_files'] == ['src/a.py', 'src/b.py']
        assert result['tests_run'] == ['test_x passed', 'test_y passed']
        assert result['decisions'] == []
        assert result['next_step'] == ''
        assert result['blocking_issues'] == []

    def test_case2_decisions_and_next_step(self):
        """Case 2: 中文格式 — 关键决策 + 下一步。"""
        stdout = (
            "关键决策:\n"
            "- 用正则不用LLM\n"
            "- 异步优先\n"
            "\n"
            "下一步: code review by Reviewer agent\n"
        )
        result = extract_handoff(stdout)
        assert '用正则不用LLM' in result['decisions']
        assert '异步优先' in result['decisions']
        assert result['next_step'] == 'code review by Reviewer agent'

    def test_case3_tests_only(self):
        """Case 3: 只有 tests_run。"""
        stdout = (
            "Tests run:\n"
            "- test_a\n"
            "- test_b\n"
            "- test_c\n"
        )
        result = extract_handoff(stdout)
        assert result['tests_run'] == ['test_a', 'test_b', 'test_c']
        assert result['changed_files'] == []

    def test_case4_empty_string(self):
        """Case 4: 空字符串。"""
        result = extract_handoff("")
        for key in ['changed_files', 'tests_run', 'decisions', 'blocking_issues']:
            assert result[key] == []
        assert result['next_step'] == ''

    def test_case5_none_input(self):
        """Case 5: None 输入 — 不抛异常，返回空结构。"""
        result = extract_handoff(None)
        for key in ['changed_files', 'tests_run', 'decisions', 'blocking_issues']:
            assert result[key] == []
        assert result['next_step'] == ''
```

- [ ] **Step 3.3: 运行 handoff 测试确认 5/5 pass**

```bash
cd E:\.hermes\hermes-agent
python -m pytest tests/agent/test_handoff.py -v --tb=long
```

期望: 5 passed

- [ ] **Step 3.4: 修改 `tools/delegate_tool.py:_run_single_child()`**

找到 `_run_single_child` 函数（约 1462 行），在收集子 agent 输出后、返回结果前加 handoff 提取：

```python
# 在 _run_single_child 的 return 之前 (约 1700+ 行):
from agent.handoff import extract_handoff

    # ... 现有子 agent 运行逻辑 ...

    # 1+4 体系 D1+D2: 提取 handoff, 父 context 不收 raw stdout
    child_stdout = getattr(child, '_last_response_text', '') or ''
    handoff = extract_handoff(child_stdout)

    result = {
        "task_index": task_index,
        "goal": goal,
        "handoff": handoff,       # 新增: 结构化 handoff
        "summary": child_stdout[:500] if child_stdout else "",  # 截断摘要
        "success": success,
        "iterations": iterations,
        "elapsed_sec": round(elapsed, 1),
    }
```

- [ ] **Step 3.5: 运行全部测试确认无回归**

```bash
cd E:\.hermes\hermes-agent
scripts/run_tests.sh -v --tb=short
```

期望: 全过, 0 fail

- [ ] **Step 3.6: Commit (流云手动)**

```bash
git add agent/handoff.py tests/agent/test_handoff.py tools/delegate_tool.py
git commit -m "refactor(1+4): D1+D2 handoff 强制压缩

引用 22 号 §三 D1+D2
extract_handoff 返 {changed_files, tests_run, decisions, next_step, blocking_issues}
父 context 只收 handoff dict, 不收 raw stdout
测试: 5/5 case pass (含 changed_files / 中文决策 / 全空 / None 异常)"
```

---

### Task 4: `config-drift-monitoring` — Config Drift Check

**Files:**
- Create: `~/.hermes/bin/config-drift-check.sh` (仓库外)
- Create: `~/.hermes/bin/update-config-baseline.sh` (仓库外)

- [ ] **Step 4.1: 创建 `~/.hermes/bin/config-drift-check.sh`**

```bash
mkdir -p ~/.hermes/bin ~/.hermes/logs
```

```bash
#!/bin/bash
# ~/.hermes/bin/config-drift-check.sh
# 1+4 体系 Q3 自我优化: 每周日 23:00 检测配置漂移
# POSIX 兼容, 仅依赖 sha256sum

set -e

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
BASELINE="$HERMES_HOME/.config-baseline.sha256"
LOG_DIR="$HERMES_HOME/logs"
TIMESTAMP=$(date -Iseconds 2>/dev/null || date '+%Y-%m-%dT%H:%M:%S%z')

FILES=(
  "$HERMES_HOME/config.yaml"
  "$HERMES_HOME/.env"
  "$HERMES_HOME/profiles/default/config.yaml"
  "$HERMES_HOME/profiles/planner/config.yaml"
  "$HERMES_HOME/profiles/coder/config.yaml"
  "$HERMES_HOME/profiles/reviewer/config.yaml"
  "$HERMES_HOME/profiles/researcher/config.yaml"
)

mkdir -p "$LOG_DIR"

# 首次运行: 创建 baseline
if [ ! -f "$BASELINE" ]; then
  for f in "${FILES[@]}"; do
    if [ -f "$f" ]; then
      sha256sum "$f" >> "$BASELINE"
    fi
  done
  echo "[$TIMESTAMP] baseline created at $BASELINE ($(wc -l < "$BASELINE") files)"
  exit 0
fi

# 后续运行: 对比 baseline
DRIFT=0
while IFS= read -r line; do
  old_hash=$(echo "$line" | awk '{print $1}')
  file=$(echo "$line" | awk '{print $2}')
  if [ -f "$file" ]; then
    new_hash=$(sha256sum "$file" | awk '{print $1}')
    if [ "$old_hash" != "$new_hash" ]; then
      echo "[$TIMESTAMP] DRIFT: $file"
      echo "  baseline: $old_hash"
      echo "  current:  $new_hash"
      DRIFT=1
    fi
  else
    echo "[$TIMESTAMP] MISSING: $file (was in baseline, now gone)"
    DRIFT=1
  fi
done < "$BASELINE"

# 检查新文件 (baseline 中没有的)
for f in "${FILES[@]}"; do
  if [ -f "$f" ] && ! grep -q "$f" "$BASELINE" 2>/dev/null; then
    echo "[$TIMESTAMP] NEW FILE: $f (not in baseline)"
    DRIFT=1
  fi
done

if [ "$DRIFT" -eq 0 ]; then
  echo "[$TIMESTAMP] OK: no config drift detected"
fi

exit $DRIFT
```

```bash
chmod +x ~/.hermes/bin/config-drift-check.sh
```

- [ ] **Step 4.2: 创建 `~/.hermes/bin/update-config-baseline.sh`**

```bash
#!/bin/bash
# ~/.hermes/bin/update-config-baseline.sh
# 手动运行以更新 baseline (配置变更后)

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
BASELINE="$HERMES_HOME/.config-baseline.sha256"

FILES=(
  "$HERMES_HOME/config.yaml"
  "$HERMES_HOME/.env"
  "$HERMES_HOME/profiles/default/config.yaml"
  "$HERMES_HOME/profiles/planner/config.yaml"
  "$HERMES_HOME/profiles/coder/config.yaml"
  "$HERMES_HOME/profiles/reviewer/config.yaml"
  "$HERMES_HOME/profiles/researcher/config.yaml"
)

> "$BASELINE"
for f in "${FILES[@]}"; do
  if [ -f "$f" ]; then
    sha256sum "$f" >> "$BASELINE"
  fi
done
echo "Baseline updated: $BASELINE ($(wc -l < "$BASELINE") files)"
```

```bash
chmod +x ~/.hermes/bin/update-config-baseline.sh
```

- [ ] **Step 4.3: 首次运行创建 baseline**

```bash
~/.hermes/bin/config-drift-check.sh
```

期望: "baseline created"

- [ ] **Step 4.4: 测试漂移检测**

```bash
echo "# test drift" >> ~/.hermes/profiles/coder/config.yaml
~/.hermes/bin/config-drift-check.sh
```

期望: "DRIFT: .../profiles/coder/config.yaml"

```bash
# 恢复
git -C ~/.hermes checkout -- profiles/coder/config.yaml 2>/dev/null || true
~/.hermes/bin/update-config-baseline.sh
```

- [ ] **Step 4.5: 加 cron**

```bash
(crontab -l 2>/dev/null || true; echo "0 23 * * 0 ~/.hermes/bin/config-drift-check.sh >> ~/.hermes/logs/config-drift.log 2>&1") | crontab -
crontab -l | grep config-drift
```

期望: 看到 `0 23 * * 0` 那行

---

### Task 5: `skill-field-sync` — Skill 字段同步

**Files:**
- Modify: `skills/agent-workflow/task-persistence/SKILL.md`

- [ ] **Step 5.1: 找到目标文件并备份**

```bash
cd E:\.hermes\hermes-agent
ls skills/agent-workflow/task-persistence/SKILL.md
cp skills/agent-workflow/task-persistence/SKILL.md skills/agent-workflow/task-persistence/SKILL.md.bak-1plus4
```

- [ ] **Step 5.2: 读取 §五 5.3 区域确定插入点**

```bash
grep -n "5.3\|5 防御话\|ACCEPTANCE\|WORKSPACE\|TIMEOUT\|DEPENDENCIES\|NO FABRICATION" skills/agent-workflow/task-persistence/SKILL.md
```

- [ ] **Step 5.3: 在 §五 5.3 加 v1.0 新增 3 字段**

在现有 5 防御话模板后追加：
```markdown
### v1.0 新增 3 字段 (22 号 §四 强化, 2026-06-25)

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `INSTALL_POLICY` | `pnpm-lock` | B2 防御: 禁止 Coder 安装新包 |
| `FORBIDDEN_FILES` | `[hermes_state.py, hermes_constants.py, hermes_logging.py]` | B5 防御: 禁止修改核心文件 |
| `VISION_REQUIRED` | `false` | 是否需要截图/视觉验证 |
```

- [ ] **Step 5.4: 在 §六 pitfall 加 D1-D5 引用**

```markdown
### D1-D5 脏上下文防御 (22 号 §三, 2026-06-25)

| 防御 | 说明 | 落点 |
|------|------|------|
| D1 | Subagent 上下文隔离 | terminal background=True, stdout 不进父 context |
| D2 | Handoff 强制压缩 | extract_handoff.py 提取结构化字段 |
| D3 | 错误 Web Pull 清理 | web_fetch 4xx/5xx 自动 context_truncate |
| D4 | Fallback 链禁止 | subagent 失败 1 次, 父级杀掉重建 |
| D5 | 飞书回流防 | [continuation] 标记, 防 5-8 条回流污染 |
```

- [ ] **Step 5.5: 在 §五 5.2.1 4 agent 能力边界表加 Q3 行**

在能力边界表的最后一行后追加：
```markdown
| **自我优化** | Q3=要 | 配置漂移监控 (config-drift-check.sh + cron 每周日 23:00) | Week 3 补 |
```

- [ ] **Step 5.6: 加 reference 行**

在文档 reference section 末尾：
```markdown
- 28 号: 4Agent 能力边界 v1.0 审查报告 (`E:\e\knowledge-vault\09-工作流编排与自动化\28-4Agent能力边界v1.0审查报告-v1.0.md`)
- 29 号: 1+4 体系实施执行文档 (`E:\e\knowledge-vault\09-工作流编排与自动化\29-1+4体系实施执行文档-v1.0.md`)
```

- [ ] **Step 5.7: 验证修改**

```bash
grep -c "INSTALL_POLICY" skills/agent-workflow/task-persistence/SKILL.md
# 期望: >= 1

grep -c "D1-D5\|脏上下文" skills/agent-workflow/task-persistence/SKILL.md
# 期望: >= 1
```

- [ ] **Step 5.8: Commit (流云手动)**

```bash
git add skills/agent-workflow/task-persistence/SKILL.md
git commit -m "refactor(1+4): task-persistence SKILL.md v1.0 字段同步

引用 22 号 §三 D1-D5 + §四 5 防御话 8 字段
§五 5.2.1 加 Q3=要自我优化闭环节
reference: 28 号 + 29 号
验证: grep INSTALL_POLICY >= 1 / grep 脏上下文 >= 1"
```

---

## 全局验证 (所有 Task 完成后)

- [ ] **V1: 全量单元测试**

```bash
cd E:\.hermes\hermes-agent
scripts/run_tests.sh -v --tb=short
# 期望: 全过, 0 fail
```

- [ ] **V2: CLI smoke**

```bash
hermes --version
hermes tools
hermes cron list
# 期望: 全 OK
```

- [ ] **V3: 5 profile ping**

```bash
hermes -p default chat "ping"
hermes -p planner chat "ping"
hermes -p coder chat "ping"
hermes -p reviewer chat "ping"
hermes -p researcher chat "ping"
# 期望: 全正常响应
```

- [ ] **V4: 4 早期信号监控**

```bash
grep -c "defensive_phrase_check_fail" ~/.hermes/logs/agent.log 2>/dev/null || echo "0"
# S1-S4 监控脚本 (25 号 §四)
```

---

## 变更记录

- 2026-06-25 v1.0: 初始实现计划, 5 capability, 预计 6-9 小时
- Base ref: `bede8fc4993b5c1ee680ee818f229f0c4e5b2684`
