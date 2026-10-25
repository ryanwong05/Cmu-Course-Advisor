# CMU Course Advisor — Bug Audit

> 审计日期：2026-10-15；实现状态更新：2026-10-16。严重度：P0 = 会生成实质错误/不完整的核心规划；P1 = 会误导用户、破坏状态一致性或造成安全/可靠性风险；P2 = 体验、命名或维护风险。

## 执行摘要

当前最危险的不是 UI 小瑕疵，而是三类可信度问题：**合法课程链无法排出、同一计划的不同 audit 给出不同数字、产品把“可转入”误写成“这个项目本身可规划”**。另外，Computational Biology minor 的已验证候选集不足以满足 choose-N，却被误报成 planning horizon 不够；结果页的手工编辑也没有回到后端 canonical state 重新审计。

当前 176 个 `unittest` 全部通过。BUG-001、BUG-002 与 BUG-003 已修复并补回归，其余条目仍说明需要更多 cross-layer invariants。

## BUG-001 — 当前 CS 主修不会自动铺设先修链

- **Severity:** P0
- **状态:** Resolved 2026-10-16
- **影响文件:** `Engine/planning.py:617-734`、`Backend/application.py:1435-1470`、`Data/processed/requirements.json:60-80`
- **复现:** freshman、Computer Science current major、无 completed courses、52-unit limit、规划到 Senior Spring。
- **Expected:** 在剩余容量内依次安排 15-112/15-122、15-150、15-210/15-251、15-213、15-451 等合法链路；若确实无法完成，应给出真实约束。
- **Actual:** 计划仍有 6 门 fixed requirements 未排：15-122、15-150、15-210、15-213、15-251、15-451；七个学期仍分别剩余 12、6、21、7、13、16、37 units。
- **Root cause:** fixed-course candidate loop 只考虑“本学期开始时先修已经满足”的 remaining courses。它不会为 current-major fixed requirements 插入必要准备课程，也不会在后续学期重新构造一条完整 prerequisite chain；已有自动 preparation 主要服务 SCS transfer profile，未通用于 current-major curriculum。
- **Smallest robust fix:** 在固定 requirement 排程前，以已有 prerequisite expression 和 completion implication 构建通用的 prerequisite closure；只加入 catalog 中存在、确实为未完成目标解锁的课程，并继续经过 offered/year/unit filters。不要写 CS 专属 course list。
- **Regression test:** `computer-science` current-major、freshman、空历史、Senior Spring；断言 6 门目标或其合法替代均排入，先修顺序正确、无重复、每学期不超 limit；若 catalog/offering 使其中一门不可排，断言诊断是具体 prerequisite/offering 原因而非笼统 horizon。
- **Implemented:** 增加通用、catalog-backed prerequisite closure，并只对 current-major flow 启用。7 个已支持 current majors 均在代表 fixture 完成；完成课程 implication 不会重新加入已满足的准备课。

## BUG-002 — 同一 CS 计划的两个 degree audit 数字不一致

- **Severity:** P1
- **状态:** Resolved 2026-10-16
- **影响文件:** `Backend/application.py:1699-1713`、`Engine/degree_audit.py:115-169`
- **复现:** 使用 BUG-001 的同一计划，比较 `degree_audits.primary_degree`、`degree_audits.selected_goal` 与 `fastest.remaining`。
- **Expected:** 对同一 current-major curriculum，primary 与 selected-goal audit 的 total/planned/unresolved 应一致，并与 planner remaining 对齐。
- **Actual:** primary audit 为 total 21 / planned 15 / unresolved 6；selected goal 为 total 21 / planned 13 / unresolved 8；planner remaining 为 6。
- **Root cause:** `build_degree_audits()` 的 `primary_curriculum` 先经过 `resolve_curriculum_requirement_options()`，但 `goal_curriculum` 直接传入原始 `goal_requirements`。原始 pattern/named-set options（例如 `15-3xx`）无法与 `_planned_course_ids()` 中的具体 course IDs 匹配，于是同一课程在 selected-goal audit 中没有被认作覆盖。
- **Smallest robust fix:** 在进入 `build_degree_audits()` 前，对 primary 和 goal curriculum 使用同一 universal resolver；或在 audit 边界统一要求 resolved curriculum。不要在 `_requirement_progress()` 内增加 program-specific special cases。
- **Regression test:** current-major 目标的 `primary_degree` 与 `selected_goal` 三个 progress 字段完全一致；另覆盖 pattern、bundle、named course set 各一个案例。
- **Implemented:** goal curriculum 与 primary curriculum 现在在 degree audit 前使用同一 universal resolver；CS fixture 的两个 audit 均为 total 21 / planned 21 / unresolved 0。

## BUG-003 — Computational Biology minor 的 choose-3 只有两个不同候选

- **Severity:** P1
- **状态:** Resolved in validation/diagnostics 2026-10-16；policy data 仍待补全
- **影响文件:** `Data/processed/program_profiles.json:28`、`Backend/requirements.py`、`Engine/planning.py:195-325`
- **复现:** Stats/ML current major + Computational Biology minor，规划到 Senior Spring。
- **Expected:** `cb-electives` 的 verified candidate set 至少包含 3 个可区分的合法 300-level Computational Biology courses；若数据不足，项目不得标为完整可规划，并应提示 candidate set 不完整。
- **Actual:** requirement 为 `choose: 3`、option 为 `02-3xx`，当前 catalog expansion 只得到 02-510 与 02-512 两个不同 course IDs。第三个 slot 不可能满足，但诊断是 `planning_horizon_exhausted`。
- **Root cause:** profile 在 promotion 时没有校验 `distinct expanded candidates >= choose`；unscheduled diagnostics 只看到 option 非空，没有检测多个 slot 竞争同一不可复用候选。
- **Smallest robust fix:** 在 data audit/promotion gate 加入 distinct-candidate cardinality check；补课程前必须核验官方 policy/catalog，不可猜测。Planner diagnostic 应识别 `insufficient_distinct_candidates`。
- **Regression test:** 所有 planner-ready choose-N groups 在扣除 bundle/重复后候选数不少于 N；人工构造不足案例必须输出明确原因且不称为 horizon exhausted。
- **Implemented:** 增加 course-disjoint candidate capacity 计算；CB minor 在目录中降级为 `needs_review`，并携带结构化 validation issue。若内部仍生成该计划，剩余 slot 明确返回 `insufficient_distinct_candidates`。没有猜测或补写新的 CMU 课程。

## BUG-004 — 广义 planning status 混淆“可转入”和“可作为当前主修规划”

- **Severity:** P1
- **状态:** Confirmed
- **影响文件:** `Backend/application.py:650-715`、`Data/processed/program_directory.json`、`Data/processed/program_coverage_report.json`
- **复现:** 查看 AI B.S.、Computational Biology B.S.、BCSA、HCI B.S.、Robotics B.S. 的 directory/API metadata。
- **Expected:** 每个 program form 的 readiness 应与用户当前选择的 flow 一致；current major 不可规划时不能只因为存在 transfer profile 就显示通用 `planning_ready`。
- **Actual:** 这 5 个 primary-major entries 可获得广义 ready 状态，但 `current_major_planning_status=directory_only`，作为 current major 请求会被阻止。Explorer 已使用 scoped flag，其他消费者仍可能误用广义字段。
- **Root cause:** broad status 使用 `has_profile or has_primary_curriculum or has_transfer_profile`，把不同产品能力压成一个布尔值。
- **Smallest robust fix:** 保留兼容字段但标为 deprecated；所有 UI/report 使用 `planner_ready` 与 `current_major_planning_status`、`transfer_planning_status` 等 scoped fields。Coverage CI 禁止用 broad status 计数。
- **Regression test:** 对上述 5 个 entry 断言 current-major planner_ready=false、transfer=true；目录页和 goal selector 不出现错误承诺。

## BUG-005 — 结果页编辑不是 canonical plan mutation

- **Severity:** P1
- **状态:** Confirmed product-state bug
- **影响文件:** `static/app.js:3325-3523`、`Backend/application.py`（缺少 plan mutation/re-audit endpoint）
- **复现:** 生成计划后换一门 requirement choice、拖动课程或添加 elective；刷新、重新打开 audit/比较，并观察后端返回的 degree audit。
- **Expected:** 一个用户动作更新唯一 plan state，重新验证 prerequisite/offering/year/units/requirement fulfillment；所有 summary、warning、comparison 与保存结果来自同一状态。
- **Actual:** replace/move/add 主要修改浏览器 DOM 和本地对象；没有后端 canonical mutation/re-audit round trip，也没有稳定 plan ID/version。不同视图可能继续展示生成时的 audit。
- **Root cause:** 当前编辑功能是在展示层增量实现，尚未建立可重放的 plan state contract。
- **Smallest robust fix:** 先定义轻量 `PlanDraft`（原始 request + ordered edits）和一个 revalidate endpoint；服务器重放 edits 后复用现有 audit，不引入账户、repository 或复杂 event-sourcing。
- **Regression test:** browser/API round-trip：replace → move → save → reload；课程顺序、units、requirements remaining 和 warnings 完全一致；非法 move 被拒绝且原状态不变。

## BUG-006 — Upload 只有单文件上限，没有批次总量上限

- **Severity:** P1
- **状态:** Confirmed security/reliability gap
- **影响文件:** `Backend/academic_history_import.py:20-93`、`Backend/application.py:1968-2028`
- **复现:** 一次上传大量、每个略低于 10 MB 的合法图片/PDF。
- **Expected:** 在读取/解码整个批次前限制文件数、总 bytes、PDF 总页数和 vision work budget。
- **Actual:** 每个文件有 10 MB 限制，PDF vision 最多 12 页，但没有 request-level 文件数/总 bytes cap；服务器仍可能承受过高内存与推理负载。
- **Root cause:** validation 位于逐文件 extractor，API 层没有 aggregate budget。
- **Smallest robust fix:** endpoint 读取前限定例如最多 8 个文件和可配置总量；限制总渲染页数，并返回 413/422 的用户可读错误。最终阈值应依据部署内存压测确定。
- **Regression test:** 文件数、总 bytes、总页数分别越界；边界值通过；错误批次不调用 extractor。

## BUG-007 — `lower_workload` 名称超过实际保证

- **Severity:** P2
- **状态:** Confirmed misleading behavior
- **影响文件:** `Engine/planning.py`、`Backend/course_metrics.py`、`Data/processed/course_metrics.json`
- **复现:** Stats/ML + Robotics additional major，比较 fastest 与 lower_workload。
- **Expected:** lower_workload 在可行约束内应有明确定义、可测的 workload objective，至少不在主要指标上明显更差。
- **Actual:** 代表运行中 lower_workload semester units 为 48/52/37/45/45/46/45，仍出现 52 units 和约 4.2 workload；实现主要限制高强度课程数量，且 metrics 含 placeholder/fallback。
- **Root cause:** 产品标签暗示全局 workload optimization，而实现只是启发式重排，输入数据也不足以支撑精确结论。
- **Smallest robust fix:** 在 metrics 未完善前改名为“balanced alternative”并展示比较指标；或定义 deterministic objective 与 tie-breaker，再加 dominance/invariant tests。
- **Regression test:** 任何标为 lower-workload 的结果必须在声明的 objective 上不劣于 fastest；数据缺失时显示不确定性。

## BUG-008 — 图片导入存在环境依赖但 setup 未完整暴露

- **Severity:** P2
- **状态:** Confirmed deployment/documentation gap
- **影响文件:** `Backend/academic_history_import.py:194-266`、`README.md`
- **复现:** 在干净环境上传 PNG/JPG；当前审计环境的 `127.0.0.1:11434` 无服务。
- **Expected:** setup 明确检查并安装 `qwen2.5vl:3b`，页面在上传前说明图片能力是否可用；文本 PDF 不受影响。
- **Actual:** 图片导入会在请求后才报告 Ollama/vision model 不可用；README 主要说明 transfer advisor 的 `qwen3:1.7b`，未形成完整 vision setup/checklist。
- **Root cause:** feature capability check 与 deployment documentation 落后于实现。
- **Smallest robust fix:** 增加启动时 capability endpoint/health indicator，README 列出 vision model；保持 local-only 与确认导入流程。
- **Regression test:** Ollama absent、model absent、malformed output、成功 extraction 四个分支；UI 根据 capability 明确降级到 text PDF/manual input。

## BUG-009 — 默认 52 units 被当作跨学院通用值

- **Severity:** P2
- **状态:** Unverified policy risk, not a proven runtime defect
- **影响文件:** `Backend/application.py:303-309`、`static/index.html:755`
- **复现:** 任意 college/year 新建计划，不修改单位上限。
- **Expected:** 产品明确说这是用户可调的 planning assumption，或从已核验的 college/year policy 得到默认值。
- **Actual:** 默认统一为 52；engine 能处理 override，但界面容易让用户把默认值理解为官方限制。
- **Root cause:** 缺少 catalog-year/college-specific enrollment policy data。
- **Smallest robust fix:** 在没有权威 policy 前改文案为“planning limit (adjustable)”并要求用户确认；未来再由带来源的 policy 数据驱动。
- **Regression test:** 不同 student contexts 的默认来源/文案可追踪；自定义限制始终被 engine 严格遵守。

## 可能问题与未验证风险

这些不能写成已确认 bug，需要补证据后处理：

- **PDF grade suffix parsing:** 正则支持 `B+`，但曾在合成 PDF 文本抽取中观察到 `B+ → B`；可能是 PDF text extraction 字符布局，不是 parser 本身。需要保存最小匿名 fixture 才能定性。
- **未来 offering 推断:** 当前 schedule/`offered` 字段不能保证未来多年开课；应把“not offered in remaining semesters”区分为 verified policy、recent history 与 unknown。
- **复杂 AND/OR、corequisite、cross-list:** engine 有表达能力，但 209 个 structured pages 并未逐个证明 semantic fidelity。
- **双重计入:** 代表路径未发现重复 course instance，但跨 major/GenEd 的“同一课程可否双重满足”是政策问题，不能只靠去重规则猜。

## 已验证没有复现的历史问题

- 21 个 entry-specific executable directory paths 中未发现同一 course 被安排两次。
- 这些路径中未发现 `total_units > unit_limit`。
- Linguistics → CS 且 completed 21-127、15-122 时，没有再次安排 21-127、15-122 或为了已完成 15-122 再安排 15-112。
- Stats/ML current-major 的 14 个 Dietrich GenEd slots 均被放入，audit unresolved 为 0。
- Experiential Learning 仍为独立 requirement，不再被 36-200 错误满足。

这些结论只针对本轮固定 fixtures，不替代浏览器 E2E 与全 catalog-year policy verification。

## 修复顺序

1. ✅ BUG-001（CS prerequisite closure）与 BUG-002（audit 单一口径）已完成。
2. ✅ BUG-003（候选 cardinality/promotion gate）已完成；官方候选数据仍待补全后再提升 CB minor readiness。
3. BUG-004（readiness 诚实展示）。
4. BUG-005（canonical edits/re-audit）。
5. BUG-006（upload aggregate limits）。
6. BUG-007～009（命名、部署和政策透明度）。
