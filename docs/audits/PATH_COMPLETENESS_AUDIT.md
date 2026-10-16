# CMU Course Advisor — Path Completeness Audit

> 审计日期：2026-10-15；实现状态更新：2026-10-16。这里的“完整”只表示在当前数据、代表学生和目标期限下，planner 把已发布的 requirement slots 放入计划；不表示获准转系、不表示正式 degree audit，也不表示未来课程一定开设。

## 评分口径

每类满分 10 分：

- 2 分：用户可以发现并选择目标。
- 2 分：requirements 有来源、结构化且正确接入。
- 2 分：planner 能生成不重复、不超容量的路径。
- 2 分：代表场景能在目标期限完成，失败时有具体原因。
- 1 分：完成课程、替代选择与 edits 能保持一致。
- 1 分：有足够的 regression/E2E 证据。

分数衡量的是当前产品成熟度，不是代码质量打分。

## 总体 scorecard

| Path type | 分数 | 当前结论 |
|---|---:|---|
| Current major | 6/10 | 71 个 primary entries 中 7 个可执行且代表场景均完整；其余绝大多数仍只可发现。 |
| Internal transfer | 7/10 | 10 个目标可执行、9 个代表场景完整；配置内最成熟，但“完成”通常指申请前置要求，不等于目标学位全程。 |
| Additional major | 4/10 | 36 个 entries 中 6 个可执行，仅 HCI 与 Robotics 的代表场景完整。 |
| Minor | 6/10 | 105 个 entries 中 8 个可执行、7 个完整；CB minor 数据集合本身不足。 |
| Undecided / exploration | 3/10 | 213 个 program forms 可浏览，但没有偏好建模、what-if shortlist 或 recommendation funnel。 |

## 代表路径实测

统一基线：freshman、无 completed courses、目标 Senior Spring、每学期上限 52 units；组合路径默认以 Stats/ML 为 current major，特别注明的除外。

| 场景 | 结果 | 关键观察 |
|---|---|---|
| Stats/ML current major | Complete | 7 个 future semesters；最大 50 units；14 个 Dietrich GenEd 均有安排；有 prerequisite-data warning。 |
| Information Systems current major | Complete | verified primary curriculum 可排完。 |
| Computer Science current major | Complete | 通用 prerequisite closure 会加入 catalog-backed 准备课程；无重复、无超限，primary 与 selected-goal audit 一致。 |
| Stats/ML → CS transfer | Complete | 5 个 semesters 到 application milestone；有 eligibility 与 prerequisite-data warning。 |
| Stats/ML → BCSA transfer/post-transfer | **Incomplete** | breadth、applications/CS electives、CFA concentration 等大量 slots 未解决。 |
| Stats/ML + Robotics additional major | Complete | 无重复、无超限；路径很密集。 |
| IS + AI additional major | **Incomplete** | 当前统一 fixture 剩 5 个 choices；各学期已接近上限，不能把本轮结果简单归因为此前截图中的空余 Senior Spring。 |
| Stats/ML + Business Administration minor | Complete | 代表组合可排完。 |
| Stats/ML + Computational Biology minor | **Incomplete** | choose-3 的 02-3xx 只展开出 2 个不同候选；数据/cardinality 问题。 |
| Linguistics → CS，completed 21-127/15-122 | Complete | 未重复安排 21-127、15-122，也没有为了已完成 15-122 添加 15-112；Linguistics 本身仍使用 Dietrich fallback reserve。 |
| Stats/ML + Robotics，max 24 | Expected incomplete | 每学期均不超过 24；9 个未排项都有显式 horizon reason。 |

在全部 21 个 entry-specific executable directory flows 中，本轮没有发现重复 course instance，也没有发现 semester `total_units` 超过 `unit_limit`。

## 1. Current major

### 真正可执行的 7 个 primary programs

- Statistics and Machine Learning B.S.
- Mathematical Sciences B.S.
- Mechanical Engineering B.S.
- Electrical and Computer Engineering B.S.
- Information Systems B.S.
- Logic and Computation B.S.
- Computer Science B.S.

7 个代表场景均完成。其余 64 个 primary entries 即便大多已有 structured extraction，也没有 promotion 成 planner-ready curriculum。

### Fallback 的含义

Linguistics 等未 promotion 的 primary major 会使用 college-level reserve（例如 Dietrich primary-major baseline），而不是实际专业课程。它让 transfer/minor 组合不至于完全忽略 current degree workload，但不能称为该专业的 degree plan。

### 必须补的能力

- 已完成通用 prerequisite closure；当前只在 current-major flow 启用，以避免改变 transfer/additional-major 的既有排程。
- promotion gate：来源、catalog year、choose-N candidate cardinality、units、nested AND/OR、capstone/timing。
- 明确区分 verified curriculum 与 college workload reserve。
- catalog-year ownership；当前主要围绕 2026–2027。

## 2. Internal transfer

### 配置的 10 个目标

AI、Computational Biology、CS、BCSA、ECE、HCI、IS、MechE、Robotics、Stats/ML。

9 个代表场景可完成 transfer requirements；BCSA 不完整。这个覆盖在“已配置 targets 内”很强，但只覆盖 71 个 primary majors 中的 10 个。

### 重要语义边界

- 默认 transfer plan 主要回答“为了申请应完成什么、何时申请”。
- `include_post_transfer_plan` 只有少数 program 有可信的 destination-degree planning 支持；不能把 transfer prerequisites complete 写成毕业路径 complete。
- admission GPA、capacity-limited、timing 等是 checkpoint，不是录取保证。
- 已完成课程 implication 的历史 bug 在 Linguistics → CS fixture 中已不复现。

### 仍需验证

- 每个 target 的 application semester 与 catalog-year policy。
- non-course constraints（portfolio、essay、advisor approval、capacity）。
- 转入后旧专业是否被替换、哪些课程可复用、是否有 residency/double-count restrictions。

## 3. Additional major

### 当前可执行

- Artificial Intelligence
- Computational Biology
- Computer Science
- Economics
- Human-Computer Interaction
- Robotics

统一代表场景只有 HCI 与 Robotics 完整。AI、CB、CS、Economics 仍有未排要求；原因混合了真实容量、候选数据、先修链与 planner 策略，不能用一个 scoring tweak 解决。

### 当前最大风险

- product 会展示已存在的 requirement groups，但未必能选择足够多的 distinct candidates。
- primary-major + additional-major 的 overlap/double-count policy 未对所有组合进行官方验证。
- “requirements placed” 不是“additional major formally declared/approved”。

## 4. Minor

### 当前可执行

AI、Business Administration、Computational Biology、CS、HCI、IS、Machine Learning、Robotics。

除 Computational Biology 外，统一代表场景均完整。CB minor 不是 unit-limit 问题，而是当前 `02-3xx` expansion 只有两个不同候选却要求 choose 3。

### 边界

- ML minor 对 SCS students 的限制已在 API 中显式阻止。
- 其他 minor 的 college/major eligibility、double-count 和 residency 限制未证明全面。
- 105 个 minor 中 97 个仍未接入 planner。

## 5. Undecided / exploration

已有 213-entry directory、college/type filters 和详情展示，适合“我知道项目名，想查它”。还不支持：

- 按兴趣、职业方向、喜欢的课程和 workload tolerance 生成 shortlist。
- 比较 major/minor 的 flexibility、overlap、switching cost。
- 从 undecided 状态保存多个候选计划并随课程完成情况更新。
- 解释“为什么推荐这个项目”，并把证据链接到官方来源。

在 verified coverage 低于 10% 时，不应推出“全校智能选专业”的承诺；可以先做 verified-program explorer。

## Requirement semantics 审计

| 能力 | 状态 | 结论 |
|---|---|---|
| Fixed course | 已实现 | completed filtering 与 current-major prerequisite closure 的 regression fixtures 均通过。 |
| Choose-N | 已实现但需 data gate | CB minor 证明 candidate cardinality 未验证。 |
| Multi-course bundle | 已实现 | `A + B` 可作为一个 option；仍需更多跨项目 fixtures。 |
| Course pattern | 已实现 | universal resolver 可展开 `16-3xx` 等；primary/goal audit 现使用同一 resolved representation。 |
| Named course set | 已实现 | 数据驱动优于在 slot builder 写 special case。 |
| Preference ordering | 已实现 | 只应改变推荐顺序，不改变官方 option set。 |
| Prerequisite AND/OR | 部分验证 | engine 支持，数据覆盖/语义未全量证明。 |
| Co-requisite | 未充分验证 | 需要专门 fixtures 与政策抽样。 |
| Course offering | 部分 | 当前/历史 evidence 不等于未来保证。 |
| Minimum year/class standing | 已接入 | 需要对实际 program rules 做来源抽样。 |
| Completion implications | 已实现 | completed-course duplicate fixture 通过。 |
| Double counting | 不充分 | 去除 duplicate course 不等于官方允许跨 requirement/program double count。 |

## Degree audit 完整性

- `primary_degree` 与 `selected_goal` 分开是正确方向。
- planned、completed、unresolved 字段也有清晰意图。
- raw/resolved curriculum 的已知不一致已修复；仍需为浏览器编辑后的 re-audit 建立 canonical state。
- `graduation_ready=false` 在 planned-but-not-completed 场景是正确的保守行为。
- college GenEd、degree minimum units、primary curriculum、goal program 应保持四个独立层，避免一个“complete”覆盖所有含义。

## Manual editing 与持久化

当前结果页支持：

- requirement choice replacement；
- 拖动课程并做本地 prerequisite/offering/year/unit 校验；
- 添加 elective；
- 将快照保存到浏览器 localStorage。

当前不完整：

- 没有后端 canonical plan ID/version；
- edits 不会统一触发 planner + degree audit；
- fixed requirement 的 remove/recovery 路径不清楚；
- 没有 undo/history、冲突处理或跨设备保存；
- comparison/advisor 可能仍基于 edit 前的 planner JSON。

因此手工编辑适合作为 prototype interaction，不适合称为稳定的“计划管理”。

## AP / IB / transfer credit

目前可以把明确等价课程作为 completed course 使用，也有 direct-equivalency metadata，但没有独立的 credit provenance 模型。MVP 前至少需要区分：

- CMU completed course；
- AP/IB placement（可能给 placement 但不等价于某门课）；
- external transfer credit；
- in-progress/planned；
- advisor-approved exception/substitution。

在没有官方 mapping 时必须保守地留给人工确认，不能把模糊 credit 自动映射为 requirement completion。

## 进入公开 MVP 前的 path acceptance criteria

1. 所有宣称 planner-ready 的 entry 都有 source、catalog year 与 promotion audit。
2. 每个 supported flow 至少有 freshman/no-history、partial-history、late-start、tight-limit 四类 fixtures。
3. 无 duplicate course、无超 unit limit、无违反已验证 prerequisite/offering/year 的 placement。
4. completed courses 永不重排；completion implications 可解释。
5. planner remaining、degree audit、UI counter 使用同一 resolved curriculum，并保持一致。
6. 所有未排要求都有具体、可行动的 reason。
7. edits 可重放、可重新审计、可恢复。
8. transfer completion 与 degree completion 在文案/API 中严格分开。
