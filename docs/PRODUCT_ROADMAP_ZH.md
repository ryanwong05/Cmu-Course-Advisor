# CMU Path 产品路线图与每日开发记录

> 维护规则：每次完成开发后，在当天条目中记录“完成内容、验证结果、遗留风险”。历史记录以 Git 提交、项目文档和已保存的项目对话为依据；无法确认的内容不写成既成事实。

## 当前产品方向

CMU Path 的核心不是简单列出毕业课程，而是回答三个不同问题：

1. **Current major**：按照现有背景，怎样完成当前学位。
2. **Internal transfer**：先规划达到转专业申请资格所需的最短路径；转入后的学位课程必须由用户主动选择继续规划。
3. **Additional major / minor**：在保留当前主修的情况下，规划额外要求，并明确重叠课程、学业压力和完成时间。

所有结果必须区分“已完成”“已经排入计划”“尚未满足”和“需要人工/院系批准”，不得把课程排入未来学期等同于学术完成。

## 每日开发记录

### 2026-08-30｜Day 1：原型启动

- 建立 CMU course path planner 初始原型。
- 搭建学生背景、目标选择和基础路径展示流程。
- 创建首个可运行版本。

验证依据：Git 提交 `1a67db9`。

### 2026-08-31｜Day 2：Robotics 与专业扩展

- 扩展 Robotics 和 major 相关数据与界面。
- 开始从单一路径原型走向多专业规划。

验证依据：Git 提交 `db247b8`。

### 2026-09-01｜Day 3：Robotics 与 Major expansion 收尾

- 延续 Robotics 与 major expansion 工作。
- 该日没有独立提交；内容并入 8 月 31 日的 Day 2 提交说明。

### 2026-09-02｜Day 4：GenEd baseline

- 修改 college baseline 与 GenEd 底层结构。
- 开始把通识要求作为独立 requirement 数据，而不是普通 elective 占位。

验证依据：Git 提交 `4d4fc0f`。

### 2026-09-03｜Day 5：Additional Major 与 Path

- 开始 additional major 路径模型与课程组合工作。
- 整理目标专业课程与当前专业课程在同一路径中的关系。
- 该日工作与 9 月 4 日共同记录在 Day 4–5 提交中。

### 2026-09-04｜Day 6：Additional Major 路径落地

- 完成 additional major 初版路径生成。
- 加入路径展示和目标课程安排。

验证依据：Git 提交 `e9c1752`。

### 2026-09-05｜Week 2：数据结构更新

- 合并 Stephen Xu 提供的课程数据更新。
- 调整课程与 requirement 数据结构。
- 为后续真实 curriculum、elective 和 prerequisite 数据接入打基础。

验证依据：Git 提交 `e8acfd1`。

### 2026-09-06｜Week 2：排课优化与 Bug 修复

- 优化课程在学期之间的安排。
- 修复路径生成和展示中的一批问题。
- 改进课程容量与学期顺序处理。

验证依据：Git 提交 `5f691bf`。

### 2026-09-07｜整理与验证

- 没有独立 Git 提交。
- 现有证据只表明该阶段在继续验证 MechE、Robotics 和课程样式；不补写无法确认的具体功能。

### 2026-09-08｜Week 3：课程与路径全面更新

- 更新课程数据和多种路径。
- 扩大可规划 major/minor 范围。
- 为 requirement choice、GenEd 与路径规则重构准备数据。

验证依据：Git 提交 `86c6030`。

### 2026-09-09｜GenEd、路径校验与比较系统

- 让 GenEd 真正进入 planner。
- 增加年级、学期和 prerequisite 移动校验。
- 修复错误弹窗无法关闭、拖动错误对象、Sophomore Spring 课程数量异常。
- 初步建立 My Paths、Rate My Path 与路径比较。
- 重构 requirement choice：Needs your choice、All requirements、Choose now、Decide later、实时进度和长列表筛选。
- 改进课程卡片可见性、对齐、颜色与 workload 表达。

验证依据：Git 提交 `9dac784` 与当天项目对话截图。

### 2026-09-10｜真实 Curriculum 与 20 个回归场景

- 补充 CS、ECE、IS、StatML、MechE 等热门 current-major curriculum。
- 扩充 additional major、minor 和 transfer 目标数据。
- 接入真实 elective 候选、课程 units、学期和 section 信息。
- 完成 Explore My Current Major 通用流程。
- 区分 scheduled 与 academically completed。
- 建立 20 个现实学生组合的 regression scenarios。
- 生成中文开发总结 Word 文档。

详细记录见 `docs/2026-09-10-work-summary-zh.md`。

### 2026-09-11｜Requirement 联动、Degree Tree 与 Transfer 模型重构

- 将 Communication、Humanities、Social Sciences、Experiential Learning 移入 Choose now。
- Requirement choice 与 Plan My Path 共用真实 elective API；选择后实时更新进度、路径和 degree tree。
- GenEd progress 改为可收起的 AND/OR audit。
- 路径结果简化为单一 Balanced workload。
- 新增类似 Stellic、但会随课程选择更新的 degree requirement tree。
- 修复拖动时误选文字的问题。
- 修复 internal transfer 被错误当成 additional major：原专业不再继续占位或被要求修完。
- 将 transfer 默认目标改为“达到申请资格”，而不是“完成转入后的整个学位”。
- 为 ECE、IS、CS、MechE 和 StatML 建立 transfer eligibility policy；展示 GPA/成绩门槛、申请时间、容量限制和官方链接。
- ECE 资格路径按官方规则包含 18-100、21-120、15-110/15-112 与 Physics I；不是只修 18-100。
- IS 资格路径包含编程要求、最低 3.5 QPA，以及 statement/interview 提醒。
- SCS/CS 显示指定课程 QPA 3.6、overall QPA 3.0、essay 和 slot availability。
- 加入 “Plan courses after I transfer” 二阶段按钮；只有毕业 curriculum 已验证的目标才显示。
- 修复 transfer prerequisite 已全部完成时 `/api/plan` 返回 409 的问题。
- 未验证 transfer policy 的项目在选择阶段禁用，避免进入最后一步才失败。
- 后端失败时在页面内显示可理解的错误提示，不再要求用户打开浏览器 Console 才能看到原因。

验证结果：87 个自动测试全部通过；浏览器实测 ECE 资格选择、资格路径生成、官方门槛展示、转入后课程二阶段按钮与页面错误日志均通过。

### 2026-09-12｜课程优先级计算修复

- 修复 planner 在计算候选课程分数时错误复用上一个循环残留 `course` 变量的问题。
- 每门候选课现在会根据自己的 `minimum_year` 和 `recommended_preparation` 计算优先级。
- 新增独立回归测试，验证具备 recommended preparation 的课程在容量有限时会获得正确优先级。
- 合并 current-major 与 transfer 中课程选项完全相同的 requirement，修复 IS 页面重复显示 15-112 的问题。
- Transfer checkpoint 新增申请课程清单，并实时标记 Completed、Scheduled 或 Still needed。
- IS 即使已由 15-112 满足申请课程要求，也会明确展示满足原因。
- CS checkpoint 按六门正式申请课程展示；15-112 单列为 preparation prerequisite，不再错误地显示成第七门申请课程。
- Transfer eligibility 路径改成真正的申请前时间轴：保留最早可申请学期、继续安排当前专业课程，并在学期末加入 “Apply for internal transfer” 里程碑；申请后的学期默认不显示。
- IS checkpoint 增加 Personal Statement、advisor interview、application deadline 和四学期申请者 graduation plan，并将整个转专业区块提升为页面最高视觉优先级。

验证结果：91 个自动测试全部通过；代码差异格式检查通过；浏览器实测 IS 已完成状态、CS 六门课程清单、Freshman Spring 当前专业课程和 transfer application 里程碑均正确，页面无运行错误。

## 后续路线

### P0｜Transfer accuracy

- 为剩余热门目标导入官方 transfer admission policy。
- 将 GPA 输入从占位说明升级为可选学生数据。
- 只给出可解释的 readiness 区间，不承诺录取概率。
- 加入申请截止日期、申请次数和课程进行中状态。
- 对 capacity-limited 项目明确显示“满足门槛不等于录取”。

### P0｜Requirement engine

- 继续导入可验证 prerequisite expression。
- 支持课程替代、permission、minimum grade、co-requisite 和重复计数限制。
- 对每项规则保存来源、catalog year 和最后验证日期。

### P1｜Post-transfer planning

- 完善 IS、ECE 之后的完整毕业路径。
- 为 CS、AI、HCI、Robotics、Computational Biology 建立独立的毕业 curriculum profile；不能把 admission requirements 当毕业要求。
- 转入前路径与转入后路径使用明显的阶段分隔。

### P1｜Product quality

- 将 20 个现实组合扩展为浏览器端端到端测试。
- 加入移动端交互、键盘操作和无障碍回归。
- 为所有 409/422 错误提供页面内可理解提示，避免要求用户查看 Console。

### P2｜Advisor intelligence

- 在有真实成绩与历史录取/容量数据后，提供可解释的 transfer readiness，而不是虚构百分比。
- 接入 AI advisor，解释风险、备选路径和下一学期最重要的行动。
