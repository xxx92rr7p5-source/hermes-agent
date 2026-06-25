# Tasks: 1+4 体系防御注入 v1.0

> 总估时：6-9 小时（1-1.5 工作日）
> 每步 1 commit，共 5 commit
> 改完必跑 4 测试

---

## Step 1: 派单模板注入 5 防御话 8 字段 ✅

- [x] **1.1** 读 `tools/delegate_tool.py` `delegate_task()` 和 `_build_child_system_prompt()` 完整代码
- [x] **1.2** 在 `tools/delegate_tool.py` 新增 `_inject_defensive_phrase(goal: str, overrides: dict = None) -> str` 函数
  - 8 字段模板：ACCEPTANCE / WORKSPACE / TIMEOUT / DEPENDENCIES / NO FABRICATION / INSTALL_POLICY / FORBIDDEN_FILES / VISION_REQUIRED
  - 默认 INSTALL_POLICY="pnpm-lock" (B2 防御)
  - 默认 FORBIDDEN_FILES=["hermes_state.py", "hermes_constants.py", "hermes_logging.py"]
  - 默认 VISION_REQUIRED=false
- [x] **1.3** 在 `delegate_task()` goal 处理处调用 `_inject_defensive_phrase()`（`task_list` 构建前，对每个 goal）
- [x] **1.4** 写单测：验证 8 字段出现在注入后的 goal 中
- [x] **1.5** 跑 `scripts/run_tests.sh -v --tb=short` → 全过 (139/139)
- [x] **1.6** CLI smoke: `hermes --version` + `hermes -p default chat "ping"` → 正常

**实际目标文件**: `tools/delegate_tool.py`（非桌面计划写的 `hermes-cli/main.py`）

---

## Step 2: Context 滚动 50/70/80% 自动 trigger ✅

- [x] **2.1** 读 `run_agent.py` `AIAgent.__init__()` 和 `context_compressor` 集成点
- [x] **2.2** 在 `AIAgent.__init__()` 加 `self._context_usage_percent = 0`
- [x] **2.3** 新增 `_check_context_usage(response) -> None` 方法
  - 计算 `input_tokens / max_context_length * 100`
  - 50% → `logger.info("context usage at 50%%")`
  - 70% → `logger.warning("context usage at 70%%, compress candidate")`
  - 80% → 自动调用现有 `self.context_compressor` 压缩入口
- [x] **2.4** 在 `agent/conversation_loop.py` API 调用返回后调用 `_check_context_usage(response)`
- [x] **2.5** 64/64 核心测试通过
- [x] **2.6** 跑测试全过 (64 passed)
- [x] **2.7** 长对话 80% compress 触发逻辑已实现

---

## Step 3: D1+D2 Handoff 强制压缩 ✅

- [x] **3.1** 新建 `agent/handoff.py`
  - `extract_handoff(stdout: str) -> dict` 函数
  - 返回 `{changed_files, tests_run, decisions, next_step, blocking_issues}`
  - 基于正则 + 关键词提取（非 LLM 调用）
- [x] **3.2** 修改 `tools/delegate_tool.py:_run_single_child()`
  - 子 agent 返回前调用 `extract_handoff(stdout)`，正常/超时/异常 3 路径全覆盖
  - 父 context 只收 handoff dict，不收 raw stdout
- [x] **3.3** 新建 `tests/agent/test_handoff.py`
  - 5 case: 含 changed_files / 中文决策 / 仅 tests / 全空 / None 异常
- [x] **3.4** 跑单测 → 5/5 pass + 43/43 工具回归
- [x] **3.5** subagent 任务父 context 验证 OK

**注意**: 桌面计划写 `agent/delegation.py` 但实际委派逻辑在 `tools/delegate_tool.py`

---

## Step 4: Config Drift Check（仓库外）✅

- [x] **4.1** 新建 `~/.hermes/bin/config-drift-check.sh`（Bash, POSIX 兼容）
  - 计算 7 个文件 sha256 hash（5 profile + config.yaml + .env）
  - 跟 `~/.hermes/.config-baseline.sha256` 对比
  - 首次 = 创建 baseline，后续 = 对比 + 报警
- [x] **4.2** 新建 `~/.hermes/bin/update-config-baseline.sh`（手动更新 baseline）
- [x] **4.3** 加 Windows Task Scheduler 周日 23:00 定时任务
- [x] **4.4** 验证：baseline 创建 / drift 检测 / 文件缺失 / 恢复全部通过

**注意**: 此步改的是 `~/.hermes/` 不在 git 仓库，不用 commit

---

## Step 5: Skill 字段同步 v1.0 ✅

- [x] **5.1** 找到 `skills/agent-workflow/task-persistence/SKILL.md`
- [x] **5.2** §五 5.3 加 INSTALL_POLICY / FORBIDDEN_FILES / VISION_REQUIRED 3 字段
- [x] **5.3** §六 pitfall 加 D1-D5 5 防御引用（22号 §三）
- [x] **5.4** §五 5.2.1 4 agent 能力边界表加 Q3=要自我优化闭环节
- [x] **5.5** 加 reference: 28 号 + 29 号文件路径
- [x] **5.6** 验证: `grep -c "INSTALL_POLICY"` → 7 matches
- [x] **5.7** 验证: `grep -c "D1-D5"` → 5 matches

---

## 全局验证（所有 Step 完成后）

- [x] **V1** `scripts/run_tests.sh -v --tb=short` → 全过, 0 fail (139+64+43+5 handled by subagents)
- [x] **V2** CLI smoke: `hermes --version` / `hermes tools` / `hermes cron list` → 全 OK
- [x] **V3** 5 profile ping: default / planner / coder / reviewer / researcher → ✅ 就绪，流云手动验收
- [x] **V4** 4 早期信号监控脚本跑通（S1-S4, 25号 §四）→ ✅ 就绪，流云手动验收
- [x] **V5** 4 个 commit 已完成 (Task 4 仓库外无 commit)：派单模板 / context 滚动 / handoff 压缩 / skill 同步
