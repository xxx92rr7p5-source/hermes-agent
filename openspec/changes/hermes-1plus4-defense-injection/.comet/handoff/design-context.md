# Comet Design Handoff

- Change: hermes-1plus4-defense-injection
- Phase: design
- Mode: compact
- Context hash: 32f4d8a8f3c97a47550850456a80423235b55fc5e4f272d28dcf74c65ee485eb

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/hermes-1plus4-defense-injection/proposal.md

- Source: openspec/changes/hermes-1plus4-defense-injection/proposal.md
- Lines: 1-58
- SHA256: fcc162517fe85bdbc1c41066f035027a4c2ea4e474c619a98562366aa5bc8933

```md
## Why

流云 1+4 体系（1 人 + CEO/Planner/Coder/Reviewer 4 Agent）已在文档层 v1.0 锁定（24-29号知识库文档），但 **hermes-agent 代码层缺少防御性派单约束**。当前 `delegate_task` 派单时，流云手敲 prompt 容易遗漏关键字段，子 agent 返回的 raw stdout 污染父 context（25号 §一 1.2 实测 ~300 token 污染），context 使用率无自动监控触发压缩。这个问题现在必须解决，因为流云已拍板 Q1-Q4，1+4 体系进入代码实施阶段（30号拍板清单）。

## What Changes

### 5 步代码改造（对应 29 号执行文档 §第一~第五步）

1. **派单模板自动注入 5 防御话 8 字段** — 修改 `tools/delegate_tool.py:_build_child_system_prompt()`，在 goal 前自动注入 ACCEPTANCE / WORKSPACE / TIMEOUT / DEPENDENCIES / NO FABRICATION / INSTALL_POLICY / FORBIDDEN_FILES / VISION_REQUIRED 模板
2. **Context 滚动 50/70/80% 自动 trigger** — 修改 `run_agent.py:AIAgent`，每次 API 调用后计算 context 占用率，50% 日志 warning，70% 提示压缩候选，80% 强制触发现有 `context_compressor`
3. **D1+D2 Handoff 强制压缩** — 新建 `agent/handoff.py`，子 agent 返回前提取 `{changed_files, tests_run, decisions, next_step, blocking_issues}`，父 context 只收 handoff dict 不收 raw stdout
4. **自我优化闭环 — Config Drift Check** — 新建 `~/.hermes/bin/config-drift-check.sh`，每周日 23:00 cron 跑，hash 对比 5 profile + config.yaml + .env 的漂移
5. **Skill 字段同步 v1.0** — 更新 `task-persistence SKILL.md` §五 加 INSTALL_POLICY / FORBIDDEN_FILES / VISION_REQUIRED 3 字段，§六 pitfall 加 D1-D5 引用

### 硬约束

- ❌ 不动 `hermes_state.py` / `hermes_constants.py` / `hermes_logging.py`（state schema / 路径常量 / 日志 schema）
- ❌ 不改 `~/.hermes/config.yaml` / `.env` / 5 profile config.yaml（流云手动）
- ❌ 不自动 git commit / push（流云手动）
- ✅ 改完必跑 4 测试（单元测试 / CLI smoke / 5 profile ping / desktop GUI）

## Capabilities

### New Capabilities

- `defensive-dispatch`: 派单时自动注入 5 防御话 8 字段模板，防止流云手敲 prompt 遗漏关键约束
- `context-rolling`: AIAgent 级别 context 占用率监控，50/70/80% 三级自动响应（warning / 候选压缩 / 强制压缩）
- `handoff-compression`: 子 agent 返回前提取结构化 handoff dict，父 context 只收摘要不收 raw stdout（D1+D2 防御）
- `config-drift-monitoring`: 5 profile + config.yaml + .env 的 sha256 hash 基线对比，每周 cron 检测配置漂移
- `skill-field-sync`: task-persistence SKILL.md v1.0 字段升级同步（INSTALL_POLICY / FORBIDDEN_FILES / VISION_REQUIRED + D1-D5 pitfall 引用）

### Modified Capabilities

<!-- No existing specs to modify — this is the first code-level defense implementation -->

## Impact

### 受影响代码

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `tools/delegate_tool.py` | 修改 | `_build_child_system_prompt()` 和 `delegate_task()` 加 8 字段注入 |
| `run_agent.py` | 修改 | `AIAgent` 类加 `_context_usage_percent` 和 `_check_context_usage()` |
| `agent/handoff.py` | **新建** | `extract_handoff()` 函数 |
| `tools/delegate_tool.py` | 修改 | `_run_single_child()` 调 `extract_handoff` |
| `tests/agent/test_handoff.py` | **新建** | 5 case 单测 |
| `~/.hermes/bin/config-drift-check.sh` | **新建** | Bash 脚本（仓库外） |
| `skills/*/task-persistence/SKILL.md` | 修改 | v1.0 字段同步 |

### 知识库引用

- 24号：AgentOps 5×3 矩阵 15 格成熟度自评（Cost + Maintainability 缺口）
- 25号：单 LLM 扩展性分析，cliff 阈值 4→8 agent，4 早期信号 S1-S4
- 26号：1+4 体系 MOC，ASCII 架构图 + 5 防御话 8 字段模板
- 27号：3 张 Mermaid 架构图谱
- 28号：12 项能力边界对照 + 4 缺口（人审门 v1.1 必修）
- 29号：完整执行文档（本文 = 29 号的代码实现）
- 30号：流云拍板清单 15 项走查
```

## openspec/changes/hermes-1plus4-defense-injection/design.md

- Source: openspec/changes/hermes-1plus4-defense-injection/design.md
- Lines: 1-192
- SHA256: c6e2645e240860e1693bb3ba4a71cf474a15843f55a49dd017e7f295d89cf39b

[TRUNCATED]

```md
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

```

Full source: openspec/changes/hermes-1plus4-defense-injection/design.md

## openspec/changes/hermes-1plus4-defense-injection/tasks.md

- Source: openspec/changes/hermes-1plus4-defense-injection/tasks.md
- Lines: 1-92
- SHA256: dffe75c1dc2fa4acf0d588dc119acca82856686a33f0f147621592d7fabdfb21

[TRUNCATED]

```md
# Tasks: 1+4 体系防御注入 v1.0

> 总估时：6-9 小时（1-1.5 工作日）
> 每步 1 commit，共 5 commit
> 改完必跑 4 测试

---

## Step 1: 派单模板注入 5 防御话 8 字段

- [ ] **1.1** 读 `tools/delegate_tool.py` `delegate_task()` 和 `_build_child_system_prompt()` 完整代码
- [ ] **1.2** 在 `tools/delegate_tool.py` 新增 `_inject_defensive_phrase(goal: str, overrides: dict = None) -> str` 函数
  - 8 字段模板：ACCEPTANCE / WORKSPACE / TIMEOUT / DEPENDENCIES / NO FABRICATION / INSTALL_POLICY / FORBIDDEN_FILES / VISION_REQUIRED
  - 默认 INSTALL_POLICY="pnpm-lock" (B2 防御)
  - 默认 FORBIDDEN_FILES=["hermes_state.py", "hermes_constants.py", "hermes_logging.py"]
  - 默认 VISION_REQUIRED=false
- [ ] **1.3** 在 `delegate_task()` goal 处理处调用 `_inject_defensive_phrase()`（`task_list` 构建前，对每个 goal）
- [ ] **1.4** 写单测：验证 8 字段出现在注入后的 goal 中
- [ ] **1.5** 跑 `scripts/run_tests.sh -v --tb=short` → 全过
- [ ] **1.6** CLI smoke: `hermes --version` + `hermes -p default chat "ping"` → 正常

**实际目标文件**: `tools/delegate_tool.py`（非桌面计划写的 `hermes-cli/main.py`）

---

## Step 2: Context 滚动 50/70/80% 自动 trigger

- [ ] **2.1** 读 `run_agent.py` `AIAgent.__init__()` 和 `context_compressor` 集成点
- [ ] **2.2** 在 `AIAgent.__init__()` 加 `self._context_usage_percent = 0`
- [ ] **2.3** 新增 `_check_context_usage(response) -> None` 方法
  - 计算 `input_tokens / max_context_length * 100`
  - 50% → `logger.warning("context usage at 50%%")`
  - 70% → `logger.warning("context usage at 70%%, compress candidate")`
  - 80% → 自动调用现有 `self.context_compressor` 压缩入口
- [ ] **2.4** 在每次 `chat.completions.create` 返回后调用 `_check_context_usage(response)`
- [ ] **2.5** 写单测：模拟不同 context 占用率验证日志/压缩触发
- [ ] **2.6** 跑 `scripts/run_tests.sh tests/agent/test_run_agent.py -v --tb=long` → 全过
- [ ] **2.7** 跑长对话验证 80% compress 触发

---

## Step 3: D1+D2 Handoff 强制压缩

- [ ] **3.1** 新建 `agent/handoff.py`
  - `extract_handoff(stdout: str) -> dict` 函数
  - 返回 `{changed_files, tests_run, decisions, next_step, blocking_issues}`
  - 基于正则 + 关键词提取（非 LLM 调用）
- [ ] **3.2** 修改 `tools/delegate_tool.py:_run_single_child()`
  - 子 agent 返回前调用 `extract_handoff(stdout)`
  - 父 context 只收 handoff dict，不收 raw stdout
- [ ] **3.3** 新建 `tests/agent/test_handoff.py`
  - 5 case: 含 changed_files / 含 tests_run / 含 decisions / 全空 / 异常 stdout
- [ ] **3.4** 跑 `scripts/run_tests.sh tests/agent/test_handoff.py -v --tb=long` → 5/5 pass
- [ ] **3.5** 跑 subagent 任务验证父 context 只看到 handoff dict

**注意**: 桌面计划写 `agent/delegation.py` 但实际委派逻辑在 `tools/delegate_tool.py`

---

## Step 4: Config Drift Check（仓库外）

- [ ] **4.1** 新建 `~/.hermes/bin/config-drift-check.sh`（Bash, POSIX 兼容）
  - 计算 7 个文件 sha256 hash（5 profile + config.yaml + .env）
  - 跟 `~/.hermes/.config-baseline.sha256` 对比
  - 首次 = 创建 baseline，后续 = 对比 + 报警
- [ ] **4.2** 新建 `~/.hermes/bin/update-config-baseline.sh`（手动更新 baseline）
- [ ] **4.3** 加 cron: `0 23 * * 0 ~/.hermes/bin/config-drift-check.sh >> ~/.hermes/logs/config-drift.log 2>&1`
- [ ] **4.4** 验证：首次运行创建 baseline → 改 1 个 profile → 再运行检测漂移 → cron 确认

**注意**: 此步改的是 `~/.hermes/` 不在 git 仓库，不用 commit

---

## Step 5: Skill 字段同步 v1.0

- [ ] **5.1** 找到 `skills/agent-workflow/task-persistence/SKILL.md`
- [ ] **5.2** §五 5.3 加 INSTALL_POLICY / FORBIDDEN_FILES / VISION_REQUIRED 3 字段
- [ ] **5.3** §六 pitfall 加 D1-D5 5 防御引用（22号 §三）
- [ ] **5.4** §五 5.2.1 4 agent 能力边界表加 Q3=要自我优化闭环节
- [ ] **5.5** 加 reference: 28 号 + 29 号文件路径
```

Full source: openspec/changes/hermes-1plus4-defense-injection/tasks.md

