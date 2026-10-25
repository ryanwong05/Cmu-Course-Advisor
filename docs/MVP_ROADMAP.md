# CMU Course Advisor — MVP Roadmap

> 更新日期：2026-10-16。目标不是一次支持 CMU 全部 213 个 program forms，而是先交付一个对明确人群诚实、可验证、能持续扩展的 MVP。

## MVP 定义

### 目标用户

第一阶段面向 CMU 大一/大二学生，重点是：

- 已支持的 7 个完整 current majors；
- 已配置的 9 个完整 internal-transfer targets；
- 已通过代表场景的 2 个 additional majors 和 7 个 minors；
- 需要把已修课转成未来学期路径、比较两个可信方案、发现风险的学生。

未 verified 的专业仍可在目录中展示，但必须标为 **Explore only / planner not verified**，不能生成看似精确的课程路径。

### MVP 核心承诺

> “对我们明确标记为 verified 的项目，系统根据已完成课程、先修、开课学期、单位上限和已核验 requirement data 生成可解释计划；不知道的地方会明确说不知道，并允许学生修改后重新验证。”

### 非承诺

- 不替代 Stellic/官方 degree audit 或 advisor。
- 不保证 admission、course availability 或 seat availability。
- 不宣称支持全部 majors/minors。
- 不让 LLM 计算 requirement fulfillment。

## 当前基线

| 指标 | 当前值 |
|---|---:|
| Directory program forms | 213 |
| Non-empty structured extraction | 209 |
| Entry-specific planner flows | 21（9.9%） |
| Representative complete flows | 16（7.5%） |
| Configured transfer targets | 10；9 个代表场景完整 |
| Automated backend tests | 176 passed |
| Browser E2E | 0 |
| CI workflow | 0 |

## P0 — MVP blocker

### 1. 修复 current-major prerequisite closure

**状态：已于 2026-10-16 完成。** 通用、catalog-backed closure 仅在 current-major flow 启用；7 个已支持 current majors 的代表场景现均可完成。

- 目标：CS current major 从 freshman/no-history 到 Senior Spring 能排出合法链，或给出真实不可行原因。
- 方法：通用 prerequisite closure，复用已有 prerequisite expression 和 completion implications；禁止 CS-specific hardcode。
- 验收：无重复、顺序正确、不超 units；6 个当前 stranded fixed courses 不再因 algorithm 缺陷遗漏。

### 2. 统一 planner、degree audit 与 UI counters

**状态：核心 resolver 不一致已于 2026-10-16 修复。** primary 与 goal curriculum 现在使用同一 option resolver；仍需把该 invariant 扩展到浏览器编辑后的状态。

- 对 primary/goal curriculum 使用同一个 resolved representation。
- 建立 invariants：`remaining == audit unresolved == UI remaining`（定义差异必须显式命名）。
- 覆盖 fixed、pattern、bundle、named set、choose-N。

### 3. 建立真实 coverage/promotion gate

**状态：choose-N distinct-candidate gate 已于 2026-10-16 完成。** 候选不足的 CB minor 现在降级为 `needs_review`，planner 诊断为 `insufficient_distinct_candidates`；其余 promotion 条件仍需逐步纳入自动 gate。

每个 planner-ready entry 必须通过：

- 官方 source URL 与 catalog year；
- 非空 fixed/groups；
- pattern/named-set 能展开；
- distinct candidates ≥ choose；
- course IDs 在 catalog；
- units/timing/eligibility 可解释；
- 至少四个代表 fixtures；
- scoped readiness 与 flow 匹配。

### 4. Canonical editable plan + revalidation

- 最小 `PlanDraft = original request + ordered edits + version`。
- replace/move/add/remove 通过后端统一重放、重新 audit。
- 保存/reload 后 summary、warnings、comparison 不漂移。
- 不需要先做账户系统或复杂数据库。

### 5. CI 与浏览器 smoke tests

- 将现有 176 tests 放入 CI。
- 明确使用 `unittest`，或正式加入 pytest dependency；不能 README 写 pytest、环境却没有。
- Playwright/等价工具覆盖：创建计划、completed 不重复、换课、移动、保存恢复、unsupported program、import review。

## P1 — Pilot quality

### 6. Screenshot/PDF import hardening

- batch 文件数/总 bytes/总 pages 限制；Ollama capability check。
- README 安装 `qwen2.5vl:3b`；模型不可用时优雅降级。
- 匿名 golden fixtures 与精度报告。
- import summary、provenance、session undo。

### 7. 扩展 verified coverage，而不是批量“打开开关”

优先按实际需求与 data quality 每批 5–10 个：

1. 修复已接入但不完整：CS current、CB minor、AI/CB/CS/Economics additional major、BCSA transfer。
2. 从 100 个 promotion candidates 中选需求最高、结构最简单、来源最明确的项目。
3. 每个项目先过 promotion gate，再在 UI 标 planner-ready。

建议优先考虑用户量大且规则相对可验证的 Dietrich/MCS/Engineering 项目；具体名单需用真实使用需求和 advisor feedback 决定，不能凭名称猜。

### 8. Product transparency

- 每个计划显示 data source、catalog year、last verified、已知缺口。
- 把 transfer prerequisite completion、major degree completion、GenEd completion、minimum units 分开。
- 把 52 units 写成 adjustable planning assumption，直到有官方分学院政策。
- `lower_workload` 在 objective 未严格定义前改成 “balanced alternative”。

### 9. Saved plan MVP

- 先做本地 versioned drafts + export/import JSON。
- 再做 PDF/CSV/ICS export 与只读 share link。
- 账户和跨设备同步放在有真实 retention 需求之后。

## P2 — Post-MVP

- Undecided recommendation funnel（兴趣/课程偏好/职业/强度）。
- 可靠 workload/FCE 数据与 license/来源策略。
- 多 catalog year、AP/IB/transfer-credit provenance、advisor exceptions。
- enrollment/section availability、waitlist、冲突检测。
- 账户、云端持久化、协作/评论。
- LLM explanation caching 与成本监控。

## 接下来两周的建议 Sprint

### Week 1 — Correctness gate

**Day 1: Freeze fixtures and invariants**

- 固定当前 16 个 Level-4 flows 和 5 个 Level-3 flows 的 JSON fixtures。
- 加全局 invariants：no duplicate、unit limit、completed not scheduled、explicit unscheduled reason。

**Day 2: CS prerequisite closure**

- ✅ 已实现通用 prerequisite closure，并限制在 current-major flow，避免改变 transfer/additional-major 行为。
- ✅ 已增加 CS current-major chain 与 completion-implication regression tests。

**Day 3: Audit consistency + choose-N validation**

- ✅ primary/goal 使用同一 resolver，已修复 6 vs 8 discrepancy。
- 加 distinct-candidate promotion check；CB minor 保守降级，直到补官方数据。

**Day 4: Scoped readiness + import safeguards**

- 清理 broad readiness 的消费点。
- 加 upload aggregate limits、Ollama capability response、README vision setup。

**Day 5: CI and browser smoke**

- CI 跑 176 tests + coverage audit。
- 浏览器 smoke 覆盖 generate/edit/reload/import-review。

### Week 2 — Canonical editing and pilot

**Day 6–7: PlanDraft/revalidate**

- 定义小型兼容 contract；重放 replace/move/add/remove。
- 所有 edits 重算 audit/warnings。

**Day 8: Persistence/export**

- versioned local draft、undo、JSON export/import。

**Day 9: Pilot instrumentation**

- 匿名记录 flow、program、成功/失败 reason、用户主动修正次数；不记录课程截图原文或身份。

**Day 10: 5–10 student pilot**

- 用真实学生任务验证：完成课导入、transfer、additional/minor、换课、解释风险。
- 收集 false confidence 与无法完成的原因，而不只看点击率。

## 4 周目标

### Week 3 — Data expansion batch 1

- 修复 6 个当前 incomplete flows。
- 从 promotion candidates 选 5 个高需求项目。
- 每个项目附 source/candidate cardinality/fixtures/reviewer。

### Week 4 — Reliability and release

- 匿名 screenshot golden set；image import 可用性检查。
- 政策与数据更新时间展示。
- 关键错误 telemetry、回滚与发布 checklist。
- advisor review 后发布 limited beta，只开放 verified flows。

## MVP release acceptance criteria

### Planning correctness

- 所有 advertised flows 的固定 regression fixtures 100% 通过。
- 0 duplicate completed/scheduled courses。
- 0 unit-limit violations。
- 已验证 prerequisite/offering/year restriction 0 violations。
- 每个 unscheduled requirement 都有具体 reason。
- planner/audit/UI counters 一致。

### Data integrity

- 每个 ready program 有 source URL、catalog year、verification status。
- choose-N candidate cardinality gate 通过。
- unsupported program 明确阻止精确 planning。
- future offerings 标为 assumption，而不是保证。

### Editing/import

- edits 可重新验证、保存、恢复、撤销。
- import 必须 review + confirm；cancel 零副作用。
- 模型/OCR 不可用时仍可手工输入。
- upload aggregate limits 与 privacy 文案存在。

### Operations

- CI 必须通过才能 merge。
- 有最低限度 error telemetry，但不收集敏感学业文件。
- 有 rollback 和 data-version release note。

## 现在应该停止做什么

- 停止把更多 raw scraped programs 直接标成 planner-ready。
- 停止在 Python/JavaScript 增加某系专属 hardcode。
- 停止大规模 architecture rewrite；先修 correctness 和 tests。
- 停止继续打磨 AI chat 文案；它不是当前核心瓶颈。
- 停止用 placeholder workload 数据作强结论。
- 停止追求“覆盖 95% 学生”的营销数字，改为量化 verified flows 与真实 pilot success。
- 停止在没有 canonical state 的情况下继续堆更多结果页编辑功能。

## 最值得做的下一项工作

**下一张任务应是统一 scoped readiness 的所有消费点（BUG-004），随后建立 canonical editable plan + revalidation（BUG-005）。**

原因：prerequisite closure、audit resolver 与 choose-N cardinality gate 已完成并通过 176 个测试。当前最小 MVP 的主要可信度风险已经转为“各入口是否诚实展示自己支持的 flow”以及“用户编辑后各视图是否仍基于同一个计划状态”。
