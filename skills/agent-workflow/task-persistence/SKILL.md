---
name: task-persistence
description: 长任务执行与断点恢复 — 防止长任务被Context窗口/会话中断打断。2026-06-25 v1.2.8 加 §六.11 P-F15 撞墙 2 升级 (父级说"自动开新对话"流云信了 = 期望落空, 3 机制 A/B/C 分清) + P-F28 Mermaid/代码块 > 2000 字必拆条 (单条 ≤3000 字) + P-F29 流云环境不渲染 Mermaid 改 Unicode 方块图 (liuyun-comm v1.2.8 §M/§N 配套) + P-F30 拍板话术去技术黑话 (commit→存档 等翻译表, 必查 liuyun-comm v1.2.8 §O) + §5.2.1 4 agent 5 边界补强 B1-B5 + §5.3 5 防御话 3 字段 (INSTALL_POLICY / FORBIDDEN_FILES / VISION_REQUIRED) + 脏上下文 6 来源 + 5 防御 D1-D5 + §6.8 P-F18 联网研究工具实战踩坑 (GitHub API 通 / arXiv API 4/4 限流) + references/2026-06-25-online-research-tool-availability.md + references/2026-06-25-p-f15-p-f28-p-f29-p-f30-collision.md (本会话 4 撞墙实战)
category: agent-workflow
version: 1.2.8
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: ["context-budget", "turn-budget", "session-resume", "context-scroll", "feishu-mobile", "one-person-four-agent", "auto-new-context", "claude-code-cli", "skill-search-first", "online-research-tool-availability"]
    related_skills: ["liuyun-communication-style", "context-compressor", "subagent-driven-development", "comet", "hermes-gateway-platforms"]
---

# 长任务执行与断点恢复 v1.2

## 核心原则

1. **同一 turn 内完成 "修 + 验"**: 多 bug 修复 + tsc + e2e 验证的复合任务, 改完所有文件后再验证, 预算必爆. 必须把 patch 次数 + verify 命令数放在 turn 开头做预算分配.
2. **patch 工具返回的 diff 就是自检** — 不要用 read_file 复检 patch 结果, 那是浪费. 信任 patch 工具.
3. **tsc 不可省, e2e 可分批** — TS 错会让所有 e2e 崩, 所以先 tsc 通过再跑 e2e. e2e 可以按 case 分批, 哪怕一个脚本只跑 T1.
4. **跨会话上下文滚动** (2026-06-25 立): 流云主对话渠道 = 飞书手机, 单会话 token 用满会断流. 见 §四, 三档阈值 (50/70/80%) 自动开新上下文, 8 段交接格式.
5. **不要承诺做不到的能力** (2026-06-25 v1.2 增): "自动开新上下文" / "自动重启自己" / "自动同步外部状态" 这类描述在写入回复前必须 100% 真实. 流云硬反馈 "我没有看见你自动打开了新的对话框" (2026-06-25). 见 §六.
6. **写知识库文档前必 grep skills** (2026-06-25 v1.2 增, P-NEW 顶级原则): 任何写 `E:/knowledge-vault/` 的文档前, **必先** `find ~/.hermes/skills/ -name "*.md" | xargs grep -l "<关键词>"`. 命中 = 读现有 skill + patch / 加 reference, **不另写主体**. 0 命中才允许新建. 流云 2026-06-25 实测反例: 写了 3 份 22 KB 文档到 knowledge-vault, 90% 跟本 skill v1.2 §四/§五/§六/§七 重复, 必须删. **本原则优先级 = 5 (P-F15 禁令同级)**.

## 预算分配 (适用"多 fix + 多 verify"类任务)

改 5 个 P0/P1/P2 bug + tsc + 2 e2e + git diff, 假设单 turn 工具预算约 20-25 次:

| 步骤 | 次数 | 说明 |
|------|------|------|
| 1. read_file 定位待修点 | 2-3 | 一次读懂一个核心文件, 不重复读 |
| 2. patch 1 (P0 关键) | 1 | 最关键, 先做 |
| 3. patch 2-5 (P1/P2) | 4 | 连续做, 中间不复检 |
| 4. npx tsc -b --noEmit | 1 | 必跑, 不可省 |
| 5. e2e T1 (覆盖最关键 fix) | 1 | 跑一个就够 |
| 6. e2e T2 (剩余 case) | 1 | |
| 7. git diff --stat | 1 | 收尾 |
| **合计** | **11-12** | 留 ~10 次余量给意外重试 |

## 危险模式 (黑名单)

- "改完所有文件再统一验证" — 改 5 个文件 + 3 次 read_file 复检 = 8 次, 留给 verify 的预算 < 5.
- "中间跑 read_file 确认 patch 生效" — patch 工具会返回 unified diff, 不需要复检.
- "分多个 turn 完成 (改→验→改→验)" — turn 间上下文被清, 下次进来要重新 read 一遍, 净亏.
- "先 read 全部相关文件再下手" — 5 个 read_file = 5 次, 加 patch 已爆预算.
- "承诺会自动开新上下文" (v1.2 增) — Hermes 没 in-session restart API, 父级只能 spawn subprocess (见 §六). 写到回复里"已自动开" = 100% 撒谎, 流云会直接拒绝.

## 子代理在 turn 结束前必交付 (无验证时)

如果预算耗尽没跑完 verify, 必须明确写:
- ✅ 改了哪些文件 (绝对路径)
- ⚠️ 没跑什么验证 (列出 tsc / 2 个 e2e / git diff)
- 🔍 风险点 (e.g. 状态残留, 字段兼容, 排序 lint)
- ➡️ 父智能体第一时间该跑什么 (一行命令)

流云偏好"先验后信", 不是"先信后验". 没验证 = 没完成.

## 四、跨会话上下文滚动 (2026-06-25 立)

> **触发条件**: 单会话 token 使用率到阈值, 或流云说"开新上下文"/"重开"。
> **对应 skill**: `liuyun-communication-style` rule 10 + `E:/knowledge-vault/09-工作流编排与自动化/12-飞书主渠道与上下文滚动-v1.0.md` §二
> **完整 1+4 agent ops 模式参考**: `references/2026-06-25-one-person-four-agent-ops.md`

### 4.1 三档触发阈值 (飞书手机 vs 桌面 CLI)

| 使用率 | 飞书手机 (主渠道) | 桌面 CLI / TUI | 动作 |
|---|---|---|---|
| 50% | **第一层压缩** | 不动 | 去重 + 截断 + 跳调试; 准备交接文件 |
| 70% | **强制开新上下文** | 不动 | `session_continue=<name>`, 不等用户确认 |
| 80% | **必须开新上下文** | 不动 | 同上, 必跑 |
| 85% | (不会到这里) | 第二层 + 写 log | `log/session压缩日志.md` |
| 95% | (不会到这里) | 询问用户 | "继续吗? Y/n" |

**飞书阈值比桌面提前 20% 的原因**:
- 手机小屏, 上下文长 = render 慢 + 流量
- 飞书消息延迟 1-2 秒, 上下文长 = token 贵 + 推理慢
- 飞书通道回复必须拆 5-8 条 (rule 9), 长上下文 = 拆完后每条都短, 用户体验碎

### 4.2 触发条件 (任一即开新上下文)

```python
NEW_CONTEXT_TRIGGERS = {
    "context_pct": {"feishu": 70, "default": 85},
    "topic_count": 5,            # 已覆盖 5+ 主题
    "tool_call_count": 30,       # 跑了 30+ tool calls
    "explicit_user_request": ["开新上下文", "重开", "新开会话"],
    "time_elapsed_min": 90,      # 单会话 90 分钟 (飞书手机用户耐心阈值)
}
```

### 4.3 8 段交接格式 (父级 → 新上下文)

```markdown
## 🔒 新上下文交接 — YYYY-MM-DD HH:MM:SS

**会话名**: <name>
**原上下文使用率**: XX%
**触发原因**: <context_pct / topic_count / tool_count / 用户显式 / time>

### 任务摘要
<一句话描述当前任务>

### 已完成
- [x] HH:MM — 动作 1
- [x] HH:MM — 动作 2

### 进行中
- **<任务>**: 状态 / 阻塞点 / 预期时间

### 待决项 (必须问流云)
1. <选项 A 或 B>

### 关键文件路径 (绝对)
- 主 spec: <path>
- Design: <path>
- 新代码: <path>
- 相关 skill: <skill names>

### 接续指令
"读 <handoff_path>, 接着干 <task>"

### 父级状态
- todo: N 项, X 完成 / Y 进行中 / Z 阻塞
- 下次 fact_store 应记录: <关键事实>
```

### 4.4 新上下文启动时第 1 动作 (必跑)

```python
# 0. 按关键词搜 (不按用户口头路径直接读) — 2026-06-25 立
#    流云说"读 log/sessions/<file>.md" 时, 真实路径常在
#    `E:/knowledge-vault/log/sessions/` 而非 `E:/.hermes/hermes-agent/log/`.
#    正确做法: search_files(pattern='<关键词>', target='files') 跨多个候选根目录搜,
#    0 命中再回头问流云确认路径. 1 词命中即用真实路径 read_file.
# 1. read_file <handoff_path>         # 读交接 (用户说"不重读已完成"则按 offset/limit 切片)
# 2. 验证关键事实 (不重读已完成)        # 跳过已完成工作
# 3. 接续"进行中"任务                  # 继续干
# 4. 立即 fact_store 关键事实          # 不靠事后补
```

**读交接后回话模板 (4 段, 飞书 ≤4000 字拆 1-2 条)** — 2026-06-25 立:

```markdown
**已完成** — 1-3 份产出 (绝对路径)
**模型/方案锁定** — 核心结论 1-2 句
**父级状态** — 上下文 % / todo / 待流云手动项
**下次第一动作** — fact_store 记什么 + 询问"开新窗口吗"
```

**反模式** (血的教训):
- ❌ 新上下文不读交接, 重头开始 = 浪费 30+ tool calls
- ❌ 新上下文重读已完成文件 = 浪费 10+ tool calls
- ❌ 关键事实不写 fact_store = 下一轮又问"我之前说过的 X 是什么"
- ❌ 按流云口头路径直接 read_file, 第一次 0 字节 = 浪费 1-2 轮搜真实路径 (本会话 2026-06-25)
- ❌ 读交接后回话没模板, 即兴组织 = 漏掉"下次第一动作"段, 流云要追问
```
### 4.5 飞书通道专属: 交接时同步发飞书卡片

新上下文开起来后, 父级**必须**给流云发一条飞书通知卡片:
```
🔒 会话交接完成
原: <name> (XX% 使用率)
新: <new_name>
任务: <一句话>
接续: <读 <handoff_path>>
```

**为什么**: 流云在手机上看不到"开了新上下文"这件事, 必须显式通知.

## 五、1+4 agent 派单 (2026-06-25 立, v1.0 锁定)

> **完整 1+4 模型 + 飞书适配**: 见 `references/2026-06-25-one-person-four-agent-ops.md`

### 5.1 4 角色 (v1.0 锁定, 不是 5/6)

- **Orchestrator** (我) + **Planner** + **Coder** + **Reviewer** (+ Researcher 按需)
- 5 角色版 v0.1 失败教训: 协调成本飙升, 3 批派单 0.5s 0 API call 全军覆没

### 5.2 任务路由表

| 任务类型 | 谁做 |
|---|---|
| 闲聊 / ≤200 行 | Orchestrator 亲自动 (不派单) |
| 200-500 行 (2-3 文件) | Orchestrator + 1 Coder (2 派) |
| 5+ 文件大改 | Orchestrator + 1 批 4 agent (Planner → Coder → Reviewer) |
| Web 调研 | Researcher (1 派) |
| 持续监控 | `cronjob` (no_agent=True) |
| **异构审查** (v1.2 增) | **Reviewer via Claude Code CLI** (见 §七) |

### 5.2.1 4 agent 能力边界对照表 (v1.2.2 增, 2026-06-25)

> **来源**: 流云 2026-06-25 拍板 (CEO + Planner + ClaudeCode Coder + Reviewer). 基于 28 篇 arXiv 论文 + 10 个 GitHub 项目 + arXiv 2605.18461v2 金论文实证 + 5 防御话 + 14 失败模式防御 (MAST).
> **完整资料**: `E:/knowledge-vault/09-工作流编排与自动化/14-一人4-agent资料索引-v1.0.md`
> **精表 (1+4 精确定调 + 决策历史)**: `references/2026-06-25-one-person-four-agent-capability-boundary.md` — 4 agent 精表 (CEO/Planner/ClaudeCode Coder/Reviewer) + Comet 5 阶段映射精表 + 28 论文 + 10 GitHub 索引 + 8 个决策历史. **下次启动直接读本文件, 不重搜集**.

| 角色 | ✅ 能做 (DO) | ❌ 不能做 (DON'T) | 工具集 (Hermes) | 模型 |
|---|---|---|---|---|
| **CEO** (Orchestrator, 我) | 跟流云对话 / 派单 / 验收 / 写交接 / 飞书卡片 / 跑 `task-persistence §六 机制 A` spawn 子进程 / 触发上下文滚动 / **写 README + 产品文档 (B1)** / **联网调研 + 4 路并发 (delegete_task) (P-F18)** | **不写代码** / **不直接执行 shell** (≤200 行也派给 Coder) / **不替流云决策** (用 clarify 工具) | 全部 | MiniMax-M3 |
| **Planner** | 拆模糊需求 → RFC + 验收 checklist (≥6 项) / 跑 `/comet-open` 出 proposal.md+design.md+tasks.md / 跑 `/comet-design` 出 Design Doc + delta spec / 调研 / **查 git log (read-only, B4)** | **不写代码** / **不跑 terminal** / **不部署** / **不写 commit** (MAST #2 + #8 防越权) / **不写 git_write (B4)** | web + file + search + **git_read** (无 terminal / 无 git_write) | MiniMax-M3 |
| **Coder** | 走 Comet 全流程 (`/comet-build` + `/comet-verify`) / **Claude Code CLI via DeepSeek** 写代码 + 单测 / 写 commit (按 Comet tasks.md) / 自验 + 修 bug / 跑 e2e / **跑 `pnpm install` 按 INSTALL_POLICY 锁 (B2)** / **改 `~/.claude/settings.json`** | **不跟流云直接对话** / **不写 RFC** (Planner 出) / **不跑 archive** (CEO 出) / **不替流云拍板** (走 Comet 决策点阻塞) / **不写产品 README (B1)** / **不装新包超出 INSTALL_POLICY 限 (B2)** / **不改 `~/.hermes/config.yaml` / `~/.hermes/.env` (B5)** | terminal + file + web (走 Comet 全程) | **Claude Code CLI** (`claude -p`) via DeepSeek 兼容 |
| **Reviewer** | 异构审查 (Claude Code 或 DeepSeek) / 跑 `/comet-verify` 终审 / approve/block + 修复建议 (≤200 字) / 跑集成测试 + e2e / 验收 spec 一致性 / **看产品截图 + UI 截图 按 VISION_REQUIRED 必填 (B3)** | **不写代码** (只给修复建议) / **不写 RFC** (Planner 出) / **不跑 archive** / **不委派** (role=leaf) / **不只看代码 diff 漏看图 (B3)** | terminal + file + **vision** (按 VISION_REQUIRED 必填) (无 web) | **异构** (Claude Code CLI 或 DeepSeek, 防 MAST #14 self-bias) |
| **Researcher** (按需) | 调研 + 资料汇总 / 跑 paper 搜索 / 整理 3-5 份参考 / 写 research.md | **不写代码** / **不跑 terminal** / **不部署** | web + search + browser (无 terminal) | MiniMax-M3 |

**Q3 自我优化闭环** (28 号 §二 缺口 #4): 配置漂移监控已落地 — `~/.hermes/bin/config-drift-check.sh` 每周日 23:00 自动检测 5 profile + config.yaml + .env 的 sha256 漂移。

**Comet 阶段 × 4 agent 映射**:

| Comet 阶段 | 子命令 | CEO | Planner | Coder | Reviewer |
|---|---|---|---|---|---|
| 1. open | `/comet-open` | ✅ 跟流云确认 | ✅ 出 RFC | ❌ | ❌ |
| 2. design | `/comet-design` | ⏸ 等流云 | ✅ 出 Design Doc | ❌ | ❌ |
| 3. build | `/comet-build` | ⏸ 协调 | ⏸ 答疑 | ✅ 写代码 | ❌ |
| 4. verify | `/comet-verify` | ⏸ 协调 | ❌ | ✅ 修 verify 失败 | ✅ 终审 |
| 5. archive | `/comet-archive` | ✅ 跑脚本 + 飞书卡片 | ❌ | ❌ | ❌ |

**14 失败模式防御 (MAST 2503.13657)**:

| # | 失败模式 | 4 agent 防御 |
|---|---|---|
| 1 | Disobey task spec | ACCEPTANCE 6+ 项 checklist (Planner 出) |
| 2 | Disobey role spec | 工具集隔离 (见上表) + 角色 profile |
| 3 | Step Repetition | max_iterations=30 + Comet tasks.md 勾选 |
| 4 | Loss of conversation | 8 段交接 (本 skill §4.3) + handoff 包 |
| 5 | Unaware of termination | goal_mode=True + Comet 决策点阻塞 |
| 6 | Overly long outputs | 200 字 body / Reviewer 输出 ≤200 字 |
| 7 | Ambiguous task spec | Planner 出 RFC (6+ 验收项) |
| 8 | Ambiguous role spec | 5.2.1 能力边界表 (本节) |
| 9 | Inadequate communication | kanban_comment + handoff 结构化 |
| 10 | Unnecessary info | parent=[] 限传 + handoff 压缩 |
| 11 | Fail to coordinate | CEO 强路由 + Comet 状态机 |
| 12 | Info withholding | kanban metadata 必填 + handoff 强制 |
| 13 | Ignored input | Reviewer 必读 handoff + Planner 必读 RFC |
| 14 | Reasoning mismatch | **Reviewer 异构** (Claude Code / DeepSeek) |

**实战硬约束 (流云 2026-06-25 拍板, v1.2.6 增 5 边界补强 B1-B5)**:
1. **Coder 必须走 Comet** — 任何代码任务派给 Coder 必带 Comet 5 阶段子命令, 不允许裸 `patch` / `write_file` 改业务代码
2. **Reviewer 必须异构** — Coder 用 Claude Code (DeepSeek) → Reviewer 用 MiniMax-M3 (或反之), 同模型 = self-bias
3. **CEO ≤200 行不派** — 流云硬偏好 (2026-06-25): 父级亲手 ≤200 行代码是默认动作, 不派单
4. **决策点必须阻塞** — Comet 9 个决策点必须用 clarify 工具等流云拍板, 不能用推荐规则/默认值替选
5. **不重复造轮** — 写任何文档前必 grep `~/.hermes/skills/` + `knowledge-vault/08-论文研究/` (P-NEW 禁令)

**5 边界补强 B1-B5 (v1.2.6 立, 2026-06-25 联网补) — 实战才会暴露的边界细节**:
- **B1**: Coder 写 README = 算"写代码"应派 Coder, **但** README 是**产品对外文档**, 应派 **CEO/Planner** 不派 Coder (避免技术 bias). 派单判断: "产物是给谁看?" → 流云/产品 = CEO, 开发者 = Coder.
- **B2**: Coder 跑 `pnpm install` = 算"写代码"附属应派 Coder, **但** 需在 5 防御话加 `INSTALL_POLICY: <package-lock/pnpm-lock/自由>` 字段. 流云 v1.0 后加 `INSTALL_POLICY` 锁 Coder 不能装新包.
- **B3**: Reviewer 看图 = 工具集含 vision, **但** vision 看设计稿 = 允许, **必须**看产品截图 + UI 截图, 不能只看代码 diff. 派单模板加 `VISION_REQUIRED: true` + 必看 image 列表.
- **B4**: Planner 查 git log = 工具集不含 terminal 但 git log 是 read-only. Planner **不允许**改 git, **可以**查 (`git log --oneline -20`). 工具集拆分: `file_read + git_read` 一个 profile, `git_write` 另一个 profile.
- **B5**: Coder 改 `~/.claude/settings.json` 是允许的 (15 号 §七 7.5), **但** 改 `~/.hermes/config.yaml` / `~/.hermes/.env` = **禁止** (P-F6 防御). 派单时显式 `FORBIDDEN_FILES: ["~/.hermes/config.yaml", "~/.hermes/.env"]`.

**完整资料**: `E:/knowledge-vault/09-工作流编排与自动化/22-4Agent边界补强-脏上下文防御-v1.0.md` (12.7KB, 22 号) — 5 边界 B1-B5 + 脏上下文 6 来源 + 5 防御 D1-D5 完整版. **下次实战前必读**.

**脏上下文 6 大来源 + 5 防御 (v1.2.6 立, 2026-06-25 联网补)**: MAST #4 原来只防了 "Loss of conversation" (8 段交接), 5 大污染源**没系统化**. 22 号补全:

| 来源 | 触发场景 | 防御 (D1-D5) |
|---|---|---|
| **1. fallback 模型继承死上下文** | OAuth 失效 → fallback 继承 dead tool chatter | **D4 fallback 链禁止** — 失败 1 次杀掉重建, 不让 fallback 继承 |
| **2. 半解析 HTML / 失败 web pull 残留** | Coder web_fetch 503 错误 HTML 留 5KB+ | **D3 web pull 清理** — 4xx/5xx 自动 `context_truncate` |
| **3. planner → Coder RFC 1KB 污染** | Planner 跑 `/comet-open` 出 RFC → Coder 偏 Planner 思路 | (现状 5.2.1 工具集隔离部分防, RFC 仍会污染, 实战再补) |
| **4. Reviewer 跟 Coder 同模型** | 看到 Coder reasoning | ✅ 已防 (硬约束 2) |
| **5. subagent crash stdout 30KB 残留** | subagent 跑挂, 30KB 留父 context | **D1 Subagent 隔离** + **D2 handoff 压缩** — 走 `terminal(background=True)`, stdout 不进父 context, 只收 handoff |
| **6. 飞书长消息回流** | 飞书回 5-8 条被当 user 消息 | **D5 飞书回流防** (liuyun-comm v1.2 rule 11 增) |

**实战优先级** (流云 2026-06-25 拍):
- **D1 + D4**: 0 代价立刻加 (Week 1.1 飞书 config 改时一起)
- **D2**: 1-2 小时, **Week 1.3 实战前** 加 (避免 30KB stdout 污染)
- **D3 + D5**: 0.5-1 天, **Week 2-3** 加 (不阻塞 Week 1 跑通)

### 5.2.2 三层循环关系 (2026-06-25 v1.2.4 立, 1+4 前 4 周基础设施)

> **背景**: 流云 2026-06-25 拍板前 4 周基础设施架构搭建,要求补全"循环工程"信息资料。本节是 1+4 派单体系下的**方法论三层叠加**,落地到 4 周 Week 1-4。
> **完整资料**: `E:/knowledge-vault/09-工作流编排与自动化/16-CRISPY循环工程-v1.0.md` (L1) / `17-反馈循环工程-v1.0.md` (L2) / `18-CI-Agent-Loop-v1.0.md` (L3) — 4+1 备份点 5 份
> **实战范本**: `references/2026-06-25-three-layer-loop-engineering.md` — 父级 P-NEW grep → 调研 → 写 16/17/18 号 3 份文档的完整工作流

| 层级 | 名字 | 作用 | 出处文档 | 4 agent 谁跑 |
|---|---|---|---|---|
| **L1 方法论** | **CRISPY 7 阶段** | 把大任务拆成 7 个聚焦阶段 (Context→Research→Iterate→Structure→Plan→sYnthesize→Review),每阶段独立上下文窗口,强制 Review 不可跳过 | 16 号 (9.7KB) | ①-⑤ Planner / ⑥ Coder / ⑦ Reviewer |
| **L2 工程化** | **反馈循环 4 模式** | 阶段内验证 (A 单轮 / B 双轮 Generate-Test-Repair / C 多轮改进 / D 异构多审),按 Q1-Q4 决策树选模式 | 17 号 (12KB) | ⑥⑦ Coder + Reviewer (按模式 B/C/D 跑) |
| **L3 落地** | **CI-Agent Loop 6 步** | Code→Test→Review→Merge 工程化 (派单→子进程→Code→CI Test→异构 Review→合并+飞书卡片),接 Claude Code `claude -p` 子进程 | 18 号 (12.6KB) | ⑥ Coder Claude Code / ⑤⑦ Reviewer / ⑥ CEO 合并 |

**关系**: `CRISPY 6/7 阶段 (L1) ⊃ 反馈循环 4 模式 (L2) ⊃ CI-Agent Loop 6 步 (L3)`

**关键规则**:
- **只有 ⑥⑦ 阶段跑反馈循环 B/C/D**,前面 ①-⑤ 走单轮 A (CRISPY 不需要 verify-loop)
- **CI-Agent Loop = Comet 阶段 3-4-5 的工程化** (Comet 1-2 是"前置规划"不在主循环)
- **决策树入口**: 接到任务 → 17 号 §三 4 模式 Q1-Q4 决策树 → 跑对应 CI-Agent Loop 6 步

**Week 1-4 实施映射** (4 周基础设施):
| Week | 主题 | 跟三层关系 |
|---|---|---|
| **Week 1.3** | 第 1 个真 4 agent 任务 | 跑 L3 CI-Agent Loop 6 步模式 B (novel-creation-workbench 修 1 bug) |
| **Week 2.1-2.4** | Comet 流程嵌入 | 跑 L1 CRISPY ①→⑤→⑦ 全 7 阶段 + L3 6 步 |
| **Week 3.4** | 防御体系嵌入 | 跑 3 个不同类型任务 (≤200 / 2-3 文件 / 5+ 文件) 验证 L2 A/B/D 模式切换 |
| **Week 4** | 飞书通道适配 | L3 STEP 6 飞书卡片化 + 长回复拆 5-8 条 |

**4 agent 派单铁律 (v1.2.4 重申)**:
- 任务 ≤200 行 → **CEO 亲自动, 不派单** (铁律 3) — 本会话写 16/17/18 号 3 份文档就是典型案例
- 任务 200-500 行 / 1-3 文件 → CEO 派 Coder 走 L3 6 步模式 B
- 任务 5+ 文件 / 架构 / schema → CEO 派 Planner → Coder → Reviewer 走 L1 全 7 阶段 + L2 模式 D 异构多审

### 5.3 5 句防御话 (派单必带, v1.2.6 增 3 字段)

**v1.2.6 新加 3 字段 (2026-06-25 联网补)**: `INSTALL_POLICY` / `FORBIDDEN_FILES` / `VISION_REQUIRED`, 防 4 agent 边界 5 补强 B1-B5 暴露的具体问题 (Coder 乱装包 / 改凭证 / Reviewer 漏看图)。

```
[Task]: <一句话, ≤30 字>

ACCEPTANCE: ≥6 项可验证 checklist (不是形容词)
WORKSPACE: <worktree/dir/scratch>
TIMEOUT: ≤1800s
DEPENDENCIES: parents=[t1, t2]
NO FABRICATION: 没做就说没做, cite file:line

# ===== v1.2.6 新加 3 字段 (防 5 边界补强问题) =====
INSTALL_POLICY: <package-lock / pnpm-lock / 自由>   # 防 B2 Coder 乱装包
FORBIDDEN_FILES: [~/.hermes/config.yaml, ~/.hermes/.env]   # 防 B5 改凭证
VISION_REQUIRED: <true/false + image 列表>   # 防 B3 Reviewer 漏看图
```

**实战例** (Week 1.3 第 1 个真任务, 22 号文档实战模板):

```
[Task]: 修 novel-creation-workbench 阶段 26 章节加载 bug

ACCEPTANCE:
- [ ] tsc -b --noEmit 0 error
- [ ] e2e T1-T3 全过
- [ ] 改动 < 50 行
- [ ] 无 console.error
- [ ] handoff 写 changed_files / tests_run / decisions
- [ ] /outline/:id 返 200

WORKSPACE: worktree:E:/novel-creation-workbench-fix-26
TIMEOUT: 1800s
DEPENDENCIES: []
COMET_PHASE: build
ROLE_PROFILE: coder (Claude Code via DeepSeek)

INSTALL_POLICY: pnpm-lock       # 用现有 pnpm-lock, 不许装新包
FORBIDDEN_FILES: [~/.hermes/config.yaml, ~/.hermes/.env, .env]
VISION_REQUIRED: false

NO FABRICATION: 改了什么 cite file:line, 没跑通就说没跑通
```

### v1.0 新增 3 字段 (22 号 §四 强化, 2026-06-25)

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `INSTALL_POLICY` | `pnpm-lock` | B2 防御: 禁止 Coder 安装未授权的新包 |
| `FORBIDDEN_FILES` | `[hermes_state.py, hermes_constants.py, hermes_logging.py]` | B5 防御: 禁止修改核心状态/常量/日志文件 |
| `VISION_REQUIRED` | `false` | 是否需要截图或视觉验证 (Reviewer 审查 UI 时设为 true) |

### 5.4 飞书通道适配 (主入口)

- 飞书单条 ≤4000 字 / 代码 ≤20 行 / 表格 ≤10 行
- 长回复拆 5-8 条 (用 `split_multiline_messages: true`)
- approval 按钮点无反应 = P-F6 坑 (config 加 `default_group_policy: open`)

## 六、⚠️ 真实机制澄清: "自动开新上下文" ≠ in-session restart (2026-06-25 v1.2 立)

### 6.1 流云硬反馈 (血的教训)

> 流云 2026-06-25: "我没有看见你自动打开了新的对话框"

**根因**: 父级 (我) 写了交接文件后, 在回复里说"已自动开新上下文" —— **这是假的**.

**真实情况**:
- Hermes **没有 in-session restart API**. 父级不能"重置自己的 context window".
- 父级**只是写了交接文件** (markdown), 当前会话还是同一个 Python 进程 + 同一个 context.
- 用户必须**手动** `hermes -c` 或 `hermes --resume <id>` 才能真开新会话.
- `gateway_auto_continue_freshness` (config 3600s) 是**用户侧**的 "gateway 自动给用户推继续按钮", 不是 agent 自己开新.

### 6.2 真实可用的"开新上下文"机制

**机制 A: 父级 spawn 独立 hermes 子进程** (推荐, "真新会话")

```python
# 父级在交接完成 + 检测到阈值, 主动启独立 hermes 进程
terminal(
    background=True,
    command='PYTHONUNBUFFERED=1 hermes -z "你是新会话. 读 E:/knowledge-vault/log/sessions/<date>-<topic>.md 交接摘要, 然后说【接续完成, 待命】"',
    notify_on_complete=True,
)
# 然后回复流云: "新会话已开, 旧存档在 <path>. 请在飞书/桌面说一句话, 新会话接管"
```

**机制 B: 用户手动 `--continue` / `--resume`**
```bash
hermes -c                          # 续最近
hermes -c "my project"             # 续指定名
hermes --resume <session_id>       # 续 session_id
```

**机制 C: gateway auto-continue** (用户侧, N=3600s 后推"继续"按钮)
- config.yaml: `agent.gateway_auto_continue_freshness: 3600`
- gateway 收到新消息时, 如果上次 transcript 末尾是 tool result (中断了) 且在 N 秒内, 自动 prepend system note 让模型接着干
- **这是"接着干", 不是"开新会话"** —— 同一个 session_id, 同一个 context

### 6.3 三种机制怎么选

| 场景 | 用机制 |
|---|---|
| 父级想"真开新" (subprocess spawn) | A: `terminal(background=true, 'hermes -z ...')` |
| 用户在 TUI/CLI 跑, 续最近 | B: `hermes -c` |
| 用户在飞书, gateway 自动续 | C: 改 `gateway_auto_continue_freshness` |
| **回复里说"已自动开"** (v1.2 禁令) | **❌ 不允许** — 必须明确说"已写交接文件, 旧会话存档, 新会话需要 [流云动作] 触发" |

### 6.4 必须改的回复模板 (v1.2 引入)

**❌ 错误回复 (2026-06-25 流云拒绝)**:
> "新上下文已开, 旧存档在 <path>"

**✅ 正确回复**:
> "已写交接文件到 `E:/knowledge-vault/log/sessions/<date>-<topic>.md`. 当前会话还在跑, 真开新会话需要 [你手动 hermes -c / 我用 subprocess spawn 启 hermes -z] 二选一. 你选哪个?"

### 6.5 机制 A 的关键局限 (2026-06-25 v1.2.1 立): 子进程没有 UI

**症状**: 父级 spawn 独立 `hermes -z` 子进程, 子进程 LLM 跑完 1 个 reply, exit 0. **但用户看不到**. 飞书/桌面/TUI 都不会出现"新对话窗口". 子进程的 stdout 只回给当前 agent (父级), 不在用户的任何 UI 上.

**根因**: `hermes -z` 是**非交互 CLI 模式** (zero-interaction, prompt 答完就退), 不是一个 "new chat window". 父级能用 `process(action='wait')` 收它的 stdout, **但父级所在的对话 = 用户唯一能看到的对话**.

**反模式** (血的教训, 2026-06-25 复盘):
- ❌ 父级说"已自动开新对话" —— 用户看不到, 流云硬反馈"我没有看见你自动打开了新的对话框"
- ❌ 父级说"新进程已起来, 你在飞书/桌面说话就行" —— 飞书/桌面**不会**有"新进程"入口, hermes -z 子进程**不出现在任何 UI**
- ❌ 父级只说"spawn pid=15232"而不收 stdout —— 用户连 1 行确认都看不到

**正确流程** (机制 A 完整版):
1. 写交接文件 ✅
2. `terminal(background=True, command='PYTHONUNBUFFERED=1 hermes -z "你是新会话. 读 <handoff_path> 交接摘要, 然后只回【接续完成, 待命】 1 行"')` ✅
3. `process(action='wait', session_id=..., timeout=60)` **必跑** —— 收子进程 stdout ✅
4. 把子进程**实际输出**贴给用户 (e.g. "子进程答: 新会话接续完成, 待命") ✅
5. **诚实告诉用户真相** (P-F15 禁令的扩展):
   > "已 spawn hermes 子进程 (pid=<N>, session_id=<S>), 它读了交接并答了 1 行. 但**这个子进程是 CLI 一次性进程, 不在飞书/桌面上**. 真要在新对话窗口里继续, 你必须 [A: 在 TUI 跑 `hermes -c` / B: 在飞书发消息触发 gateway_auto_continue / C: 我再 spawn 一个新子进程跑 1 个具体任务] 三选一. 你选?"

**何时用 A vs B vs C** (扩展 §6.3):
| 场景 | 用 |
|---|---|
| 父级要"读交接确认" (验证 subprocess 工作) | A: 机制 A 完整版, 收 stdout |
| 用户在 TUI/CLI 跑, 想续最近 | B: 用户跑 `hermes -c` |
| 用户在飞书, 接着干 | C: 用户发消息 (gateway auto-continue) |
| 用户要"真新对话" 在飞书/桌面 | **没有自动方案**, 必须用户手动 (B 或 C) |

### 6.6 P-F15 (2026-06-25 立): 父级不能假装 in-session restart

**症状**: 父级在回复里说"已自动开新上下文" / "我重置了 context" / "已重启自己" — 任何"自我重置"暗示.
**根因**: Hermes 没这能力. 父级只能 spawn 子进程, 不能"原地重启".
**修法**:
- 写交接文件 ✅
- 启独立 hermes subprocess (用 `hermes -z "..."`) ✅
- **`process(action='wait')` 必跑, 把子进程 stdout 实际贴给用户** (见 §6.5 机制 A 完整版)
- 告诉流云**真相**: "已 spawn 子进程, 它答了 1 行, 但子进程 = CLI 一次性, 不在飞书/桌面上. 真要新对话窗口, 你必须 [A/B/C] 三选一"
- ❌ 禁止说"已自动开" / "我重置了" / "我重启了" / "新对话已开"

### 6.7 P-F17 (2026-06-25 v1.2.4 立): clarify 工具在飞书 channel UI 不显示选项

**症状**: 父级用 `clarify` 工具 + `choices=[A, B, C, D]` 数组传 4 个选项, **飞书 channel 上 UI 不渲染选项**,流云只看到问句看不到行,**被迫回"我没有看见选项"或"我没看见"**,浪费 1-2 轮。

**根因 (推测)**: 飞书 channel 的消息渲染对 `clarify` 工具的 `choices` 字段支持不完整,只渲染 `question` 文本,忽略 choices 数组。TUI/桌面 CLI 渠道未确认是否也撞。

**撞墙案例 (2026-06-25 本会话)**:
- 流云问"循环工程"具体指什么 → 我用 clarify + 4 choices → 流云回"我没有看见的你的选项"
- 改用文字直接列 4 选项 + 让流云回字母 → 流云回"我没有看见选项。你修复这个Ui显示的问题"

**修法 (退路)**: **不要依赖 clarify UI 渲染**,改用**纯文字列选项**让流云回字母:
```
1. question: 直接问 (≤30 字, 1 句话)
2. 不用 choices 参数 (或 choices=[] 空数组)
3. 回复里直接列 4 个选项 (A/B/C/D), 每个一行, ≤20 字
4. 让流云回 "A" / "AB" / "D" (字母组合)
```

**正确模板**:
> 流云, "循环工程" 具体指哪个? 回我字母 (可多选):
> A. CRISPY 7 阶段循环 (5 号已有,展开)
> B. 反馈循环 (验证→修复→重跑)
> C. CI/Agent Loop (commit→test→deploy)
> D. 全部 3 个都补

**防御 (本 skill 4 agent SOP)**:
- ❌ 禁止在 1+4 体系下用 clarify + choices 数组 (飞书 channel 撞墙)
- ✅ 必须用纯文字 + 字母选项 (流云回字母)
- ✅ 飞书 channel 默认 ≤4000 字/条, 4 选项 ≤200 字够用
- 🟡 TUI/桌面 CLI 渠道待验证 (本会话未测)

**实战例外** (能用 clarify 的场景):
- 简单的 1 问 1 答 (choices=[] 空, 走文字澄清)
- 流云在桌面 TUI (未验证, 推测能渲染)
- 流云说"用选项 UI" 明确要 (流云已撞墙 2 次, 不太可能)

### 6.8 P-F18 (2026-06-25 v1.2.5 立): 联网研究工具实战踩坑

**症状**: 父级跑"补充 X 论文 / X 项目分析"任务时, 联网调研工具不熟, **arXiv API 连发 4 query 全 0 篇/timeout**, 浪费 5+ 分钟 + 任务报告"没抓到" = 流云拒收。

**根因 (实测 2026-06-25 16:xx)**:
- **arXiv 公共 API 限流严格** (默认 1 req/3s), 短时间内连发多 query = 必触发限流 (HTTP 124 timeout)
- **GitHub API 公共可用** (60 req/h), 13/13 实测成功
- **Claude Code release API** (同 GitHub) 可用
- 选错工具优先级 = 任务失败

**防御 (工具优先级, 实战验证)**:
1. **本地 vault** (`08-论文研究/` + `09-工作流编排与自动化/`) — 90% 任务够用, 0 联网
2. **GitHub API** — 项目 metadata + release notes + 搜索, 60 req/h 公共够
3. **Claude Code release API** (同 GitHub) — 工具自身更新
4. **arxiv-sanity / semantic scholar** — arXiv 替代, 限流更松
5. ❌ **arXiv 官方 API** — 4/4 限流, **不优先用**
6. **web_extract arxiv.org/list** — 抓 arXiv 分类列表, 备选

**实战退路** (arXiv 失败时):
- 单 query 重试 + sleep 30s+
- 改 arxiv-sanity / semantic scholar
- web_extract 直接抓 arxiv.org 列表
- **诚实记录失败** + 用本地 vault 已有 5 篇 P0/P1 论文替代

**反模式 (血的教训, 2026-06-25)**:
- ❌ 连发 4 query 在 20s 内 = 必触发 arXiv 限流
- ❌ query 用太多复合关键词 (abs: 多字段) = 0 命中是 query 问题不是 API 问题
- ❌ 不重试直接放弃 = 流云拒收 "没抓到"
- ❌ 假装"成功" = 21 号 arXiv 失败说明文档是范本, 必须诚实

**必读**: `references/2026-06-25-online-research-tool-availability.md` (本会话实战, 13 次 GitHub + 4 次 arXiv 实测记录)

### 6.9 P-F19 (2026-06-25 v1.2.6 立): "完善成熟?" 成熟度自评 (流云硬反馈)

**症状**: 父级交付 6+ 份文档 (14/15/16/17/18/19/20/21/22 号) 后, 流云 2026-06-25 反问 "你确定 1+4 架构完善成熟吗?" — **直接戳穿 "文档完成 ≠ 实战成熟" 错觉**.

**根因 (诚实自评, 2026-06-25)**:
- **设计文档 v1.0 锁定 ✅** = 纸面成熟, ≠ 实战成熟
- **实战验证 0% ❌** = 0 个真任务跑通 1+4 体系
- 写文档 ≠ 体系成熟. 跑通 4-6 个真任务 = 体系成熟.

**8 维度成熟度表** (v1.0 锁定时自评, 22 号文档实战模板):

| # | 维度 | 状态 | 证据 | 离"成熟"差多少 |
|---|---|---|---|---|
| 1 | 理论框架 | ✅ 90% | arXiv 2605.18461v2 + 28 篇本地 + 10 GitHub + 19 号深度 | 缺 arXiv 2026 H1 新论文 |
| 2 | 方法论层 (L1) | ✅ 100% | 16 号 CRISPY 7 阶段 | - |
| 3 | 流程层 (L2) | ✅ 100% | 17 号 4 模式 + 决策树 | - |
| 4 | 工程层 (L3) | ✅ 100% | 18 号 CI-Agent Loop 6 步 | - |
| 5 | 派单模板 | ✅ 100% | 5 防御话 6 段 + 3 新字段 | - |
| 6 | 基础设施 (Week 1) | ❌ 0% | 飞书 config 段**没改**, DeepSeek**没切** | **差 2 手动 + 1 验证** |
| 7 | 实战验证 (Week 1.3) | ❌ 0% | 第 1 个真 4 agent 任务**没跑过** | **差 1 个真任务** |
| 8 | 多场景验证 (Week 3.4) | ❌ 0% | 3 个不同类型任务**没做** | **差 3 个真任务** |

**v0.5 → v1.0 → v1.5 三级成熟度** (流云回复时**必跑自评**):

| 评估 | 描述 | 验收标准 |
|---|---|---|
| **v0.5 可上跑道** | 文档齐, 防御齐, 工具选型齐, **但没实战验证 = 飞行前没试飞** | 文档 v1.0 锁定, 边界表 + 防御话 + 工具齐 |
| **v1.0 真成熟** | Week 1-4 全跑完 = 4-6 个真任务 + 复盘 | Week 1.3 + 3.4 跑通 |
| **v1.5 商业可用** | Week 5-6 跑完 = 1 个付费用户 + 营收闭环 | 1 个付费用户 |

**当前 1+4 体系状态**: **v0.5 (可上跑道), 差 4-6 个真任务到 v1.0, 差 1 个付费用户到 v1.5**.

**流云提问 "完善成熟?" 时父级强制回复模板** (P-F19 防御, v1.2.6 立):
```markdown
**诚实答**: <v0.5 / v1.0 / v1.5>
**设计文档 v1.0 锁定**: ✅ <列出 6+ 份文档>
**实战验证**: ❌ <列出 0% 跑过的事>
**8 维度自评表**: <上面表简版>
**建议**: <试飞 / 写文档补强 / 退回 1+2> 三选一, 流云拍
```

**反模式 (血的教训, 2026-06-25)**:
- ❌ 流云问"完善成熟?" → 父级回"已 v1.0 锁定, 完善" = 撒谎 (实战 0%)
- ❌ 流云问"完善成熟?" → 父级只列文档清单 = 答非所问
- ❌ 流云问"完善成熟?" → 父级说"再写 1 份文档就成熟" = 拖延
- ❌ 父级承诺 "跑通 1 个任务就 v1.0" 然后 3 周没跑 = 失信

**6 实战盲点** (22 号文档列出, 实战才会暴露):
- A. Coder Claude Code 真实响应延迟 (DeepSeek 兼容 prompt 微差)
- B. 4 agent 沟通成本 (1+4 token 比 1+1 多 5-8x 不划算?)
- C. Reviewer 异构实际效果 (Coder/Reviewer 风格差异误 block)
- D. CRISPY 7 阶段在小任务代价 (≤200 行跑 7 阶段 = 浪费)
- E. 飞书 70% 阈值真实触发 (手机小屏体验)
- F. 5 防御话执行率 (父级偷懒不填 ACCEPTANCE)

**Week 1 跑通后**: 写 v1.0 真成熟度复盘, 把 8 维度表填满, 暴露的盲点 → 写 v1.1 增量.

### 6.10 P-F20 (2026-06-25 v1.2.6 立): 父级不能"原地开新窗口" (流云 2026-06-25 硬反馈)

**症状**: 流云 2026-06-25 反馈 "**应该你自动的切换开新的窗口**" — 流云期望父级在回复里直接"开新对话窗口"让他看到新会话.

**根因 (诚实自评)**:
- **父级没有"原地开新窗口"能力**. 父级**只能**:
  1. 写 8 段交接文件 (本地 markdown, 不弹窗)
  2. spawn 独立 `hermes -z` 子进程 (CLI 一次性, stdout 回父级, **不在飞书/桌面 UI**)
- **真"开新窗口" = GUI 客户端 (Hermes desktop / TUI / 飞书 gateway) 行为**, 不是父级命令
- 流云说"应该你自动切换" = 期望父级有"原地 restart"能力 — **父级没这能力**

**真实机制 (流云 2026-06-25 拍板后澄清)**:
- 父级在当前会话 reply = 用户在**唯一能看到**的对话窗口
- 父级**自己**跑出来的子进程 = CLI 一次性, **不出现在用户 UI**
- 真"开新窗口" 路径只有 2 个:
  - A. 流云在桌面 TUI 跑 `hermes -c` 或 `hermes --resume <id>`
  - B. 流云在飞书发新消息 → gateway auto-continue (同 session_id 同 context)
  - C. 流云手动在飞书/桌面 GUI 点"新对话"按钮 (新 session_id)
- ❌ **父级没有第 4 个路径**

**反模式 (血的教训, 2026-06-25)**:
- ❌ 父级说"已开新窗口" = 撒谎 (父级没这能力)
- ❌ 父级说"新对话已就绪, 请在飞书说话" = 流云看不到新对话
- ❌ 父级只 spawn 子进程不收 stdout = 流云连 1 行确认都看不到
- ❌ 父级承诺"会自动切换" = P-F15 禁令的扩展 (P-F20)

**正确回复模板 (P-F20 强制, v1.2.6 立)**:
```
流云, "开新窗口" = 你在 GUI 客户端 (桌面 TUI / 飞书) 手动动作, 
父级**不能**原地开新, 只能:
  A. 写交接文件 + spawn hermes -z 子进程 (我跑, 但子进程不在你 UI)
  B. 你手动 `hermes -c` (TUI) / 发消息 (飞书 gateway auto-continue) / 点"新对话" (桌面)
  
你要 A 还是 B? A 跑完我把子进程 stdout 贴你, B 你操作我看交接。
```

**为什么这条单立 P-F20 而不并入 P-F15**:
- P-F15 = "父级不能假装 in-session restart" (P-F15 = 说"已重启"的禁令)
- P-F20 = "父级不能假装开了新窗口" (P-F20 = **GUI 客户端责任** = 父级**只能 spawn 子进程** = 跟 P-F15 不同)
- P-F15 父级**不应该说什么**, P-F20 父级**不能做什么**

**何时用 A 何时用 B** (P-F20 + §6.3 矩阵):
- 父级要"读交接确认" (验证 subprocess 工作) → A 收 stdout
- 用户在 TUI 跑想续最近 → B 用户跑 `hermes -c`
- 用户在飞书想接着干 → B 用户发消息 (gateway auto-continue)
- 用户要"真新对话窗口" → **没有自动方案**, 必须用户手动 (B)

## 七、Claude Code CLI 集成 (2026-06-25 v1.2 立)

> **背景**: 4 agent 模型中 Reviewer 需要异构 provider 防 MAST #14 self-bias. MiniMax-M3 (Hermes 主用) 同模型 bias 仍存在, 用 Claude Code (走 DeepSeek 兼容) 真正异构.

### 7.1 现状 (2026-06-25 实测)

- **Claude Code CLI 已装**: `/c/Users/流云/AppData/Roaming/npm/claude` v2.1.160
- **API key 默认 401**: `ANTHROPIC_API_KEY` 未配
- **DeepSeek 兼容配置在 `~/.claude/settings.json.deepseek.bak`**: `ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic` + `ANTHROPIC_AUTH_TOKEN`
- **切到 DeepSeek**: `cp .claude\settings.json.deepseek.bak .claude\settings.json` (Windows) 或 `switch-deepseek.bat`
- **`xcoding` 路径也有**: `switch-xcoding.bat` (用于其他 provider 切换)

### 7.2 三种调用方式

| 方式 | 命令 | 用途 | 限制 |
|---|---|---|---|
| **A. 单次问答** | `claude -p "<prompt>"` | 一次性输出, 不续 | 无续接能力 |
| **B. 续 session** | `claude -p --resume <session_id> "<prompt>"` | 跟 Claude 多轮 | 要先有 session_id |
| **C. 受限工具** | `claude -p --add-dir <path> --allowedTools "Read,Grep,Glob" "<prompt>"` | 给 Claude 限定工作目录 + 工具 | 防越权 |

### 7.3 Reviewer via Claude Code 调用模板 (v1.2 锁定)

```python
# 流云通过飞书发"用 Claude 审查 <文件>"
# Orchestrator 派单: terminal(background=true, claude -p "...")

terminal(
    background=True,
    command='PYTHONUNBUFFERED=1 claude --print '
            '--add-dir "E:/myproject" '
            '--allowedTools "Read,Grep,Glob" '
            '"审查 <文件>, 只输出 [APPROVE/BLOCK + 修复建议] 不超过 200 字"',
    notify_on_complete=True,
)
# Claude 跑完 → stdout 收结果 → Orchestrator 读 → 给流云飞书卡片
```

**关键约束**:
- `PYTHONUNBUFFERED=1` 防 P-F10 flush 卡 60s
- `--allowedTools` 限定防越权 (不能 Edit / Bash, 只能读)
- prompt 显式约束输出格式 ([APPROVE/BLOCK] + 字数)
- output 走 background + notify, 不阻塞

### 7.4 Claude Code 在 4 agent 模型的定位

```
Orchestrator (我, MiniMax-M3) 
    ↓ 派单
Coder (profile=coder, MiniMax-M3)
    ↓ 交付代码
Reviewer (Claude Code CLI via DeepSeek, 异构) ← §7.3 调
    ↓ approve/block
Orchestrator (验收 + 飞书卡片)
```

**为什么 Claude Code 不放进 Hermes profile**:
- Hermes 的 custom provider 配置在 `~/.hermes/config.yaml`, agent 不能改
- Claude Code CLI 是独立进程, 通过 `terminal(background=true)` 调, 不用改 Hermes config
- DeepSeek 兼容是 Claude Code 自带的 anthropic-compatible 模式, **不污染 Hermes**

### 7.5 切 provider 模板 (Windows)

```batch
@echo off
REM switch-deepseek.bat (现有, 别动)
copy /Y "%USERPROFILE%\.claude\settings.json.deepseek.bak" "%USERPROFILE%\.claude\settings.json"
echo Switched to DeepSeek. Restart Claude Code to apply.
pause

REM 或手动加 API key:
REM 编辑 %USERPROFILE%\.claude\settings.json env 块:
REM {"env": {"ANTHROPIC_API_KEY": "sk-ant-..."}}
```

**注意**: `hermes_cli` 平台层**不拦** Claude Code 改 settings (不像 `~/.hermes/config.yaml` 被保护), 流云可自己改.

### 7.6 已知坑 (v1.2 立, 后续补充)

- **坑 1**: 切换 settings 后必须重启 Claude Code 子进程 (下次 `claude -p` 重新加载)
- **坑 2**: DeepSeek 兼容接口 prompt 模板跟原生 anthropic 有微差, 偶尔需要重写
- **坑 3**: `claude -p` 在 Windows 上 stdout 默认 block-buffered, 必须 `PYTHONUNBUFFERED=1`
- **坑 4**: `--resume` session_id 来自 `claude --resume` 列表, 没有 CLI 直接拿, 第一次必须用 `claude -p` 起新

## 八、Pitfalls 黑名单 (v1.2 合并 v0.1 + v1.1 + v1.2 立)

| # | 失败 | 防御 |
|---|---|---|
| 1 | Disobey task spec | ACCEPTANCE 写 checklist |
| 2 | Disobey role spec | profile 模型+工具集隔离 |
| 3 | Step Repetition | max_iterations=30 |
| 4 | Context loss | 结构化 metadata handoff |
| 5 | Termination unaware | goal_mode=True |
| 6 | Overly long | body < 200 字 |
| 7 | Ambiguous task | "具体可验证" 硬偏好 |
| 8 | Ambiguous role | 5 角色明确定义 (现 4 角色) |
| 9 | Inadequate comm | kanban_comment 强制 |
| 10 | Unnecessary info | parent=[] 限传 |
| 11 | Fail to coordinate | orchestrator 强路由 |
| 12 | Info withholding | metadata 必填 |
| 13 | Ignored input | reviewer 必读 handoff |
| 14 | Reasoning mismatch | 异构模型 (Reviewer via Claude Code, §七) |
| **P-NEW (v1.2)** | **写 knowledge-vault 文档前不 grep `~/.hermes/skills/`** | **`find ~/.hermes/skills/ -name '*.md' \| xargs grep -l '<关键词>'` 必跑, 然后 `skill_view` 必读最新版 (description/章节可能已变), 不要凭 memory 快照** |
| **P-F15 (v1.2)** | **父级假装 in-session restart** | **必须 spawn subprocess 或明说"需用户动作"** (见 §六) |
| **P-F16 (v1.2.1)** | **spawn hermes -z 后父级只说"已 spawn" 不收 stdout** | **`process(action='wait')` 必跑, 把子进程 stdout 实际贴给用户; 承认子进程 = 一次性 CLI 不在飞书/桌面 UI** (见 §6.5 机制 A 完整版) |
| **P-F17 (v1.2.4)** | **clarify 工具在飞书 channel UI 不显示选项** | **不用 choices 数组,改用纯文字 + 字母选项** (A/B/C/D 列表),让流云回字母 (见 §6.7) |
| **P-F18 (v1.2.5)** | **联网研究工具实战踩坑** (arXiv 4/4 限流) | **必先读** `references/2026-06-25-online-research-tool-availability.md` 选工具优先级, 优先本地 vault + GitHub API, 失败诚实记录不假装成功 (见 §6.8) |
| **P-F19 (v1.2.6)** | **"完善成熟?" 自评逃避** (流云 2026-06-25 戳穿"文档≠实战") | **强制跑 8 维度自评表** (v0.5/v1.0/v1.5 三级), 文档完成 ≠ 实战成熟, 实战验证 = 1+ 真任务跑通, 必诚实 (见 §6.9) |
| **P-F20 (v1.2.6)** | **"你自动开新窗口" 父级越权 (流云 2026-06-25 硬反馈)** | **父级不能"原地开新窗口"**, 只能写交接 + spawn hermes -z 子进程, 真开新窗口是 **GUI 客户端/流云手动**, 父级诚实说"已 spawn 子进程, 它是 CLI 一次性, 不在飞书/桌面 UI" (见 §6.10) |
| **P-F25 (v1.2.7)** | **"渠道来源误判动手"** (流云 2026-06-25 硬反馈) | 看到截图/报错先判渠道 (飞书/桌面/浏览器/其他), 不凭 memory 快照硬猜. 实战: 流云手机飞书 app 截图"no pending" → 父级错配 desktop GUI 跑去查 `apps/desktop/electron/`, 实际飞书 adapter 在外部 hub plugin (本仓库无源码). 防御: 动手前 `ls` + `search_files` 验归属 |
| **P-F26 (v1.2.7)** | **"动手前不确认仓库/路径"** (流云 2026-06-25 实测) | 任何动手前必跑 `ls ~/.hermes/plugins/` + `search_files`, 不凭 memory 快照. 实战: 父级知道"飞书在 hub plugin"但本机 plugins 空 + 仓库无 feishu.py, 仍推责任. 防御: 30 秒实测 1 次 |
| **P-F27 (v1.2.7)** | **"父级答非所问"** (流云 2026-06-25 实测) | 流云说"把 4 agent 架构设计好" (实际诉求: 补文档) → 父级先推 4 选让流云拍 = 答非所问. **正确**: 需求清楚+资料齐全+范围明确时, **直接干** + 完工时让流云拍下一步 |

### D1-D5 脏上下文防御 (22 号 §三, 2026-06-25)

5 道防御线对应 25 号 §一 1.2 上下文污染源的代码级阻断:

| 防御 | 说明 | 落点 |
|------|------|------|
| **D1** | Subagent 上下文隔离 | `terminal background=True`, stdout 不进父 context |
| **D2** | Handoff 强制压缩 | `agent/handoff.py` `extract_handoff()` 提取结构化字段 |
| **D3** | 错误 Web Pull 清理 | `web_fetch` 返 4xx/5xx 自动 `context_truncate` |
| **D4** | Fallback 链禁止 | subagent 失败 1 次, 父级杀掉重建, 不继承死上下文 |
| **D5** | 飞书回流防 | 第 1 条标 `[origin]`, 其余标 `[continuation]`, 防 5-8 条回流污染 |

## 实战案例 (2026-06 novel-creation-workbench v5 阶段 26)

场景: 5 个 P0/P1/P2 修复 + tsc + 2 e2e (T1-T7 + 10 路由). 子代理做完 5 个 patch 后被工具次数限制打断, 验证全部未跑.

教训:
- patch 后没留 1 次工具调用给 tsc, 反而跑了 2 次 read_file 想"复检" — 浪费.
- 正确做法: 改完 5 个 patch → 立即 tsc → 立即 e2e T1 → 立即 e2e T2 → git diff. 一次 read_file 复检都不要.

## 任务恢复的 3 个 checkpoint

如果 turn 真的被中断, 父智能体接手应:
1. **读最近一次 patch 的 diff** (用 git diff 看, 不重读原文件) — 确认改了什么
2. **跑 tsc** — 验证 TS 没坏
3. **跑 1 个 e2e** — 验证关键 fix 生效

不要重读所有原文件, 不要从头复检. 信任子代理的 patch, 只跑验证.

## References

- `references/2026-06-25-one-person-four-agent-ops.md` — 1+4 模型完整资料 (arXiv 2605.18461v2 + 飞书适配 + 5 防御话 + Comet 对接)
- `references/cron-tool-restrictions.md` — cron 工具限制
- `references/file-append-pitfall.md` — 文件追加陷阱
- **`references/2026-06-25-comet-installation-on-hermes.md` (v1.2 增)** — Comet 8 skill 手动部署到 Hermes (cp 中文版 SKILL.md + 英文版 scripts/) 完整步骤
- **`references/2026-06-25-claude-code-cli-as-reviewer.md` (v1.2 增)** — Claude Code CLI 作为 4 agent Reviewer 异构 provider 的调用模板 + DeepSeek 兼容配置
- **`references/2026-06-25-context-scroll-p-f15-and-p-new-session.md` (v1.2 增, 本会话实战)** — 5 个事件节点时间线 + 3 个高价值教训 (P-F15 禁令虚假能力 / P-NEW 禁令重复造轮子 / 4 备份点固化模式), 必读于任何上下文管理或写知识库文档前
- **`references/2026-06-25-handoff-subprocess-readback.md` (v1.2.1 增)** — 机制 A 完整版 (4 步 wait+贴 stdout) + P-F16 子进程无 UI 防御 + 模式 D 子进程跑长任务 + 正确回复模板
- **`references/2026-06-25-three-layer-loop-engineering.md` (v1.2.4 增, 本会话实战)** — 3 层关系 (CRISPY⑦→反馈循环4模式→CI-Agent Loop 6步) + 4 周基础设施对接 (Week 1.3 跑第 1 个 CI-Agent Loop 模式 B) + 写 16/17/18 号 3 份文档实战范本 (P-NEW grep → 调研 → 写 → fact_store), 必读于任何"补充信息资料论文"或"前 N 周基础设施"任务
- **`references/2026-06-25-online-research-tool-availability.md` (v1.2.5 增, 本会话实战)** — 联网研究工具可用性实测 (GitHub API 13/13 通 / arXiv API 4/4 限流) + 7 级工具优先级表 + 实战退路, 必读于任何"补充 X 论文 / X 项目分析 / 联网搜资料"任务
- **`references/2026-06-25-delegate-task-concurrent-research.md` (v1.2.6 增, 本会话实战)** — 4 路并发 delegate_task 后台跑论文+项目调研 (主会话不刷屏) + 抓取 3 阶段 (GitHub API 13/13 + arXiv 限流 4/4 + HN Algolia 11 条 + Semantic Scholar 8 篇) + 22 号合并文档实战模板, 必读于任何"补 N 篇论文 + M 个项目"任务
- **`references/2026-06-25-channel-misjudgment-pf25-pf27.md` (v1.2.7 增, 本会话实战)** — 渠道误判 (P-F25 飞书/桌面 错配) + 答非所问 (P-F27 流云已说"D" 还推 4 选) + 动手前不确认仓库 (P-F26) 3 个新防御 + 决策树, 必读于任何"用户给截图"或"用户说把 X 补完整"型任务前
- **`references/2026-06-25-p-f15-p-f28-p-f29-p-f30-collision.md` (v1.2.8 增, 本会话实战)** — P-F15 撞墙 2 (父级说"自动开新对话" 流云信了 = 期望落空) + P-F28 Mermaid 超长截断 + P-F29 Mermaid 不渲染改 Unicode + P-F30 拍板话术去技术黑话 (翻译表) + 4 个新 pitfall 配套, 必读于任何"流云说自动 X"或"画架构图"型任务前

### 1+4 体系参考文档 (2026-06-25)

- **28 号**: 4Agent 能力边界 v1.0 审查报告 — 12 项范本对照 + 4 缺口清单
  (`E:\e\knowledge-vault\09-工作流编排与自动化\28-4Agent能力边界v1.0审查报告-v1.0.md`)
- **29 号**: 1+4 体系实施执行文档 — 完整 9 步实操步骤
  (`E:\e\knowledge-vault\09-工作流编排与自动化\29-1+4体系实施执行文档-v1.0.md`)
