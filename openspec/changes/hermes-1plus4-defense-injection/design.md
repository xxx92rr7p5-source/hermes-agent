# Design: 1+4 体系防御注入 v1.0

> 本文性质：技术 RFC，定义 5 步改造的架构决策、集成点、数据流。
> 配套：proposal.md（WHY）+ tasks.md（执行清单）
> 知识库基线：24-29号 v1.0 文档

---

## 一、架构总览

```
流云手敲 prompt
  │
  ▼
delegate_task(goal, context, toolsets)        ← tools/delegate_tool.py:2074
  │
  ├─ _inject_defensive_phrase(goal)           ← [NEW] 8 字段模板注入
  │
  ▼
_build_child_system_prompt(injected_goal)     ← tools/delegate_tool.py:665
  │
  ▼
Child AIAgent.run()                           ← run_agent.py:333
  │
  ├─ _check_context_usage(response)           ← [NEW] 50/70/80% trigger
  │
  ▼
Child returns stdout
  │
  ├─ extract_handoff(stdout)                  ← [NEW] agent/handoff.py
  │
  ▼
Parent receives handoff dict (NOT raw stdout)
```

## 二、Step 1: 派单模板注入

### 2.1 注入点选择

**决策**：在 `delegate_task()` 中 goal 进入 `_build_child_system_prompt()` 之前注入，而非在 `_build_child_system_prompt()` 内部注入。

**理由**：
- `_build_child_system_prompt` 是通用 prompt 构建器，不应耦合防御逻辑
- 注入发生在 `delegate_task` 层面，所有派单路径（单任务 + 批量）统一覆盖
- 流云手敲的原始 goal 保持不变，8 字段以结构化前缀追加

### 2.2 8 字段模板格式

```
[Task]: <流云原始 goal>

ACCEPTANCE: (≥6 项可验证 checklist)
WORKSPACE: <自动检测或默认>
TIMEOUT: <从 config 读取或默认 1800s>
DEPENDENCIES: parents=[]
NO FABRICATION: 没做就说没做, cite file:line, 不编 PR / id
INSTALL_POLICY: pnpm-lock
FORBIDDEN_FILES: [hermes_state.py, hermes_constants.py, hermes_logging.py]
VISION_REQUIRED: false
```

### 2.3 实现函数

```python
def _inject_defensive_phrase(goal: str, overrides: dict = None) -> str:
    """在 goal 前注入 5 防御话 8 字段模板。
    默认值从 delegation config 读取，可通过 overrides 覆盖。
    """
```

- **位置**：`tools/delegate_tool.py`，作为模块级辅助函数
- **调用点**：`delegate_task()` 函数中，task_list 构建前对每个 goal 调用
- **默认值来源**：`_load_config()` 的 delegation section 扩展字段

## 三、Step 2: Context 滚动 50/70/80%

### 3.1 集成策略

**决策**：在现有 `context_compressor` 上叠加监控层，不替代压缩机制。

**理由**：
- `run_agent.py` 已有成熟的 `context_compressor`（`context_compressor.py` 2500+ 行）
- 50/70/80% 阈值是**监控和触发**逻辑，压缩本身复用现有基础设施
- 新增 `_check_context_usage()` 作为轻量 wrapper

### 3.2 实现位置

- `AIAgent.__init__()`: 加 `self._context_usage_percent = 0`
- 每次 `chat.completions.create` 返回后：调用 `_check_context_usage(response)`
- 阈值行为：
  - **50%**: `logger.warning("context usage at 50%")` — P-F15 软信号
  - **70%**: `logger.warning("context usage at 70%, compress candidate")` — 强信号
  - **80%**: 自动调用 `self.context_compressor` 的压缩入口

### 3.3 计算公式

```python
context_usage_pct = (response.usage.input_tokens / max_context_length) * 100
```

`max_context_length` 从 model metadata 读取（已有 `model_metadata.py`）。

## 四、Step 3: D1+D2 Handoff 强制压缩

### 4.1 Handoff 数据结构

```python
@dataclass
class Handoff:
    changed_files: List[str]      # 修改的文件列表
    tests_run: List[str]           # 运行的测试
    decisions: List[str]           # 关键决策
    next_step: str                 # 下一步建议
    blocking_issues: List[str]     # 阻塞问题
```

### 4.2 extract_handoff 实现策略

**决策**：基于正则 + 关键词的结构化提取，非 LLM 调用。

**理由**：
- LLM 提取增加 token 成本和延迟
- 子 agent 已被告知按特定格式输出（`_build_child_system_prompt` 第 696-705 行已要求结构化输出）
- 正则提取可确定性测试，5 case 覆盖

### 4.3 父 context 隔离

- `_run_single_child()` 返回前调用 `extract_handoff(stdout)`
- 返回结果中 `stdout` 字段替换为 `handoff` dict
- 父 agent 的 `delegate_task` 返回 JSON 中，每个 task result 含 `handoff` 字段

## 五、Step 4: Config Drift Check

### 5.1 脚本设计

```bash
#!/bin/bash
# ~/.hermes/bin/config-drift-check.sh
# POSIX 兼容，无外部依赖（仅 sha256sum + diff）

FILES=(
  "$HOME/.hermes/config.yaml"
  "$HOME/.hermes/.env"
  "$HOME/.hermes/profiles/default/config.yaml"
  "$HOME/.hermes/profiles/planner/config.yaml"
  "$HOME/.hermes/profiles/coder/config.yaml"
  "$HOME/.hermes/profiles/reviewer/config.yaml"
  "$HOME/.hermes/profiles/researcher/config.yaml"
)

BASELINE="$HOME/.hermes/.config-baseline.sha256"
```

### 5.2 行为

- **首次运行**：创建 baseline，输出 "baseline created"
- **后续运行**：逐文件 sha256 对比 baseline
- **漂移检测**：输出差异表（哪个文件 / hash 变化），写 `logs/config-drift.log`
- **Cron**：`0 23 * * 0`（每周日 23:00）

## 六、Step 5: Skill 字段同步

### 6.1 修改目标

- `skills/agent-workflow/task-persistence/SKILL.md`：
  - §五 5.3 加 INSTALL_POLICY / FORBIDDEN_FILES / VISION_REQUIRED 3 字段
  - §六 pitfall 加 D1-D5 5 防御引用（22号 §三）
  - §五 5.2.1 4 agent 能力边界表加 Q3=要自我优化闭环节
  - 加 reference: 28 号 + 29 号文件路径

## 七、硬约束检查

| 约束 | 状态 |
|------|------|
| 不动 `hermes_state.py` | ✅ 不改 |
| 不动 `hermes_constants.py` | ✅ 不改 |
| 不动 `hermes_logging.py` | ✅ 不改 |
| 不改 `~/.hermes/config.yaml` | ✅ 流云手动 |
| 不改 `.env` | ✅ 流云手动 |
| 不自动 commit/push | ✅ 流云手动 |
| 每步 ≤5 文件 | ✅ Step 3 最多（3 文件：handoff.py + delegate_tool.py + test_handoff.py） |
| 改完跑 4 测试 | ✅ 每步验证 |

## 八、风险与缓解

| 风险 | 缓解 |
|------|------|
| `delegate_tool.py` 2900+ 行，改动引入回归 | 仅注入型改动，不改现有逻辑路径 |
| context_compressor 已复杂，叠加可能冲突 | 只在 80% 阈值调用现有入口，不加新压缩逻辑 |
| extract_handoff 正则误提取 | 5 case 单测覆盖（含全空/异常），子 prompt 已要求结构化输出 |
| 仓库有 16 个未提交文件（含目标文件） | 先 `git stash` 或确认现有改动与本次无关 |
| 22 号文档不在知识库 | 防御逻辑定义已内化在 24-29 号文档中，字段定义明确 |
