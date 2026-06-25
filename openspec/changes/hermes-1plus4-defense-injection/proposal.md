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
