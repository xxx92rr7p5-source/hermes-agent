---
comet_change: hermes-1plus4-defense-injection
role: technical-design
canonical_spec: openspec
---

# Technical Design: 1+4 体系防御注入 v1.0

> 日期：2026-06-25
> 关联 OpenSpec change: `hermes-1plus4-defense-injection`
> 知识库基线：24-29号 v1.0 文档

---

## 1. Capability: `defensive-dispatch` — 派单模板注入

### 1.1 注入点

**位置**: `tools/delegate_tool.py`
- `_inject_defensive_phrase()` — 新增模块级函数
- `delegate_task()` 第 2183-2188 行 — 修改 goal 处理

### 1.2 函数签名与实现

```python
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

    幂等：如果 goal 已以 '[Task]:' 开头，跳过注入。
    默认值从 delegation.defensive_phrase config 读取。
    """
    if goal.lstrip().startswith('[Task]:'):
        return goal

    cfg = _load_config()
    defense = cfg.get('defensive_phrase', {})

    params = {
        'goal': goal.strip(),
        'workspace': os.getenv('TERMINAL_CWD', ''),
        'timeout': defense.get('timeout', 1800),
        'install_policy': defense.get('install_policy', 'pnpm-lock'),
        'forbidden_files': ', '.join(defense.get('forbidden_files',
            ['hermes_state.py', 'hermes_constants.py', 'hermes_logging.py'])),
        'vision_required': str(defense.get('vision_required', False)).lower(),
    }
    if overrides:
        params.update(overrides)

    return _DEFENSIVE_TEMPLATE.format(**params)
```

### 1.3 调用位置

`delegate_task()` 中 goal 进入 `_build_child_system_prompt` 之前：

```python
# 单任务路径 (≈2183行):
task_list = [{"goal": _inject_defensive_phrase(goal), ...}]

# 批量任务路径 (≈2173行):
for t in tasks:
    t["goal"] = _inject_defensive_phrase(t["goal"])
```

### 1.4 默认值设计

| 字段 | 默认值 | 来源 | 可覆盖 |
|------|--------|------|--------|
| WORKSPACE | `$TERMINAL_CWD` | 环境变量 | ✅ |
| TIMEOUT | `1800` | config `defensive_phrase.timeout` | ✅ |
| INSTALL_POLICY | `pnpm-lock` | config `defensive_phrase.install_policy` | ✅ |
| FORBIDDEN_FILES | `[hermes_state.py, hermes_constants.py, hermes_logging.py]` | config | ✅ |
| VISION_REQUIRED | `false` | config | ✅ |

---

## 2. Capability: `context-rolling` — Context 滚动 50/70/80%

### 2.1 注入点

**位置**: `run_agent.py`
- `AIAgent.__init__()` — 加 `_context_usage_percent` 和 `_model_max_context`
- `AIAgent._check_context_usage()` — 新增方法
- 主 API 调用循环 — 每次 `chat.completions.create` 返回后调用

### 2.2 函数签名

```python
# AIAgent.__init__ 新增属性:
self._context_usage_percent = 0
self._model_max_context = 128000  # fallback，从 model_metadata 读

def _check_context_usage(self, response) -> None:
    """50/70/80% 三级 context 占用监控。

    50% → logger.info (软信号)
    70% → logger.warning (压缩候选)
    80% → 自动触发现有 context_compressor
    """
    if not (hasattr(response, 'usage') and response.usage):
        return

    input_tokens = response.usage.input_tokens
    max_ctx = getattr(self, '_model_max_context', 128000)
    if max_ctx <= 0:
        return

    pct = int(input_tokens / max_ctx * 100)
    self._context_usage_percent = pct

    if pct >= 80:
        logger.warning("context usage at %d%%, triggering forced compression", pct)
        self._trigger_context_compression()
    elif pct >= 70:
        logger.warning("context usage at %d%%, compress candidate", pct)
    elif pct >= 50:
        logger.info("context usage at %d%%", pct)

def _trigger_context_compression(self) -> None:
    """调用现有 context_compressor 的压缩入口。"""
    cc = getattr(self, 'context_compressor', None)
    if cc and hasattr(cc, 'compress'):
        try:
            cc.compress()
        except Exception as exc:
            logger.error("context compression failed: %s", exc)
```

### 2.3 精确调用点确定

需要在实际代码中定位 API 调用循环。候选位置：
- `agent/agent_runtime_helpers.py` 的 `_call_api()` 或类似函数
- `run_agent.py` 的 `run()` 主循环
- 搜索 `chat.completions.create` 调用点

---

## 3. Capability: `handoff-compression` — D1+D2 Handoff 提取

### 3.1 文件结构

```
agent/handoff.py          # 新建 — extract_handoff() + Handoff dataclass
tests/agent/test_handoff.py  # 新建 — 5 case 单测
tools/delegate_tool.py    # 修改 — _run_single_child() 调用 extract_handoff
```

### 3.2 Handoff 数据结构

```python
from dataclasses import dataclass, field, asdict

@dataclass
class Handoff:
    changed_files: list = field(default_factory=list)
    tests_run: list = field(default_factory=list)
    decisions: list = field(default_factory=list)
    next_step: str = ""
    blocking_issues: list = field(default_factory=list)
```

### 3.3 正则模式（中英双语）

| 提取目标 | 正则模式 | 提取方式 |
|---------|---------|---------|
| changed_files | `(?:files?\s*(?:created\|modified\|changed)\|(?:创建\|修改\|更改)(?:了)?(?:文件)?):` | bullet list (`- item`) |
| tests_run | `(?:tests?\s*(?:run\|executed\|passed\|failed)\|(?:测试\|运行)(?:了)?):` | bullet list |
| decisions | `(?:decisions?\|key\s*decisions?\|(?:关键)?(?:决策\|决定)):` | bullet list |
| next_step | `(?:next\s*steps?\|下一步):\s*(.+?)(?:\n\n\|\n\*\|\n-\|$)` | 单行捕获 |
| blocking_issues | `(?:blocking\s*issues?\|issues?\s*encountered\|(?:问题\|阻塞)):` | bullet list |

### 3.4 异常安全

```python
def extract_handoff(stdout) -> dict:
    if not stdout or not isinstance(stdout, str):
        return asdict(Handoff())
    try:
        # ... 提取逻辑
        return asdict(handoff)
    except Exception:
        return asdict(Handoff())  # 永不抛异常
```

### 3.5 调用点修改

`tools/delegate_tool.py:_run_single_child()` 返回前：

```python
from agent.handoff import extract_handoff

# 子 agent 完成后，≈1720行:
result = {
    "task_index": task_index,
    "goal": goal,
    "handoff": extract_handoff(child_output),  # 新增
    "summary": child_output[:500],              # 截断摘要而非 raw stdout
}
```

### 3.6 测试用例

| # | 输入 | changed_files | tests_run | decisions | next_step | blocking_issues |
|---|------|--------------|-----------|-----------|-----------|-----------------|
| 1 | "Files changed:\n- src/a.py\n- src/b.py\n\nTests run:\n- test_x passed" | `["src/a.py", "src/b.py"]` | `["test_x passed"]` | `[]` | `""` | `[]` |
| 2 | "关键决策:\n- 用正则不用LLM\n- 异步优先\n\n下一步: code review" | `[]` | `[]` | `["用正则不用LLM", "异步优先"]` | `"code review"` | `[]` |
| 3 | "Tests run:\n- test_a\n- test_b\n- test_c" | `[]` | `["test_a", "test_b", "test_c"]` | `[]` | `""` | `[]` |
| 4 | `""` (空字符串) | `[]` | `[]` | `[]` | `""` | `[]` |
| 5 | `None` | `[]` | `[]` | `[]` | `""` | `[]` |

---

## 4. Capability: `config-drift-monitoring` — 配置漂移监控

### 4.1 脚本结构

```bash
#!/bin/bash
# ~/.hermes/bin/config-drift-check.sh
# POSIX 兼容。sha256sum 对比 7 个配置文件的 hash。

HERMES_HOME="$HOME/.hermes"
BASELINE="$HERMES_HOME/.config-baseline.sha256"
LOG_DIR="$HERMES_HOME/logs"

FILES=(
  "$HERMES_HOME/config.yaml"
  "$HERMES_HOME/.env"
  "$HERMES_HOME/profiles/default/config.yaml"
  "$HERMES_HOME/profiles/planner/config.yaml"
  "$HERMES_HOME/profiles/coder/config.yaml"
  "$HERMES_HOME/profiles/reviewer/config.yaml"
  "$HERMES_HOME/profiles/researcher/config.yaml"
)

# 首次运行 = 创建 baseline
if [ ! -f "$BASELINE" ]; then
  mkdir -p "$(dirname "$BASELINE")"
  for f in "${FILES[@]}"; do
    [ -f "$f" ] && sha256sum "$f" >> "$BASELINE"
  done
  echo "baseline created at $BASELINE"
  exit 0
fi

# 后续运行 = 对比
mkdir -p "$LOG_DIR"
DRIFT=0
while IFS= read -r line; do
  hash=$(echo "$line" | awk '{print $1}')
  file=$(echo "$line" | awk '{print $2}')
  if [ -f "$file" ]; then
    new_hash=$(sha256sum "$file" | awk '{print $1}')
    if [ "$hash" != "$new_hash" ]; then
      echo "[$(date -Iseconds)] DRIFT: $file (baseline: $hash, current: $new_hash)"
      DRIFT=1
    fi
  else
    echo "[$(date -Iseconds)] MISSING: $file"
    DRIFT=1
  fi
done < "$BASELINE"

[ "$DRIFT" -eq 0 ] && echo "[$(date -Iseconds)] OK: no config drift detected"
```

### 4.2 Cron 配置

```
0 23 * * 0 ~/.hermes/bin/config-drift-check.sh >> ~/.hermes/logs/config-drift.log 2>&1
```

---

## 5. Capability: `skill-field-sync` — Skill 字段同步

### 5.1 修改目标

文件：`skills/agent-workflow/task-persistence/SKILL.md`

| 位置 | 修改 | 内容 |
|------|------|------|
| §五 5.3 | 加 3 字段 | INSTALL_POLICY / FORBIDDEN_FILES / VISION_REQUIRED |
| §六 pitfall | 加 D1-D5 引用 | 22号 §三 5 防御描述 |
| §五 5.2.1 | 加 Q3 行 | Q3=要自我优化闭环节 |
| reference | 加 28/29 号 | 28 号 + 29 号文件路径 |

---

## 6. 跨 Capability 设计决策

### 6.1 错误处理原则

- **注入层**：永不改变原始 control flow，注入失败 = 用原始 goal 继续
- **监控层**：异常吞噬 + logger.error，不阻塞主逻辑
- **提取层**：异常安全，返回空结构不抛异常

### 6.2 测试策略

| Capability | 测试类型 | 文件 |
|-----------|---------|------|
| defensive-dispatch | 单元测试 | `tests/tools/test_delegate_tool.py` |
| context-rolling | 单元测试 | `tests/agent/test_run_agent.py` |
| handoff-compression | 单元测试 (5 case) | `tests/agent/test_handoff.py` |
| config-drift-monitoring | Bash 手动验证 | `~/.hermes/bin/` |
| skill-field-sync | grep 验证 | `skills/.../SKILL.md` |

### 6.3 硬约束

```
❌ 不动: hermes_state.py / hermes_constants.py / hermes_logging.py
❌ 不改: ~/.hermes/config.yaml / .env / 5 profile config.yaml (流云手动)
❌ 不自动: git commit / push (流云手动)
✅ 每步: ≤5 文件，≤200 行增量
```
