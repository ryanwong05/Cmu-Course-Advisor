# CMU Path 2026 年 9 月 10 日开发总结

## 一、今天的目标

今天的工作重点是把 CMU Path 从“能够展示规划原型”推进到“能够使用真实 requirement 数据生成并检查课程路径”。核心目标包括：

1. 让 Requirement Choice 页面只展示真正需要用户决定的内容。
2. 让 current major、转专业、additional major 和 minor 使用统一的真实规划逻辑。
3. 补全热门专业及辅修的 requirement profile。
4. 建立一组现实学生组合的回归测试，防止修改一个专业时破坏另一个专业。
5. 修复选课、学期限制、prerequisite、弹窗和课程卡片展示中的问题。

## 二、Requirement Choice 页面重构

Requirement Choice 页面已经从大量同尺寸空白卡片，改成以“当前需要用户完成的决定”为中心的流程。

### 新页面结构

- 页面标题改为 **Finish your course choices**。
- 增加说明：**Only decisions that still affect your plan are shown here.**
- 增加实时进度，例如 `6 of 10 decisions complete`。
- 默认显示 **Needs your choice**。
- 增加 **All requirements** audit 视图。
- 将 requirement 分为：
  - **Choose now**：会阻塞当前路径生成的决定。
  - **Decide later**：未来需要完成，但暂时不阻塞规划的决定。
- 已完成或系统自动满足的项目不再占据主决策页面。
- 长课程列表只在展开 requirement 后显示搜索和筛选。
- 每个收起的 requirement 行统一显示名称、选择规则、状态或截止时间和展开箭头。
- 选择或取消课程后，进度、状态和后续生成计划会同步更新。

### 数据与交互

- 页面使用真实 requirement 数据，不是静态演示界面。
- 已接回 completed courses、课程选择保存、路径生成和 prerequisite checking。
- Requirement 的紧迫程度由 minimum year、deadline 和 planning logic 判断。
- 保留键盘操作和正确的展开状态属性。
- 完成桌面与移动端布局适配。

## 三、课程规划界面改进

### Requirement 与 Plan 分页

Requirement Choice 和最终课程 Plan 保持为两个独立页面，避免用户在同一页面同时处理先决条件和学期课程卡片。

Requirement 选择进度会被带入 Plan 页面，并在用户修改课程后持续更新。

### 课程卡片与使用说明

- 已选课程采用与推荐课程一致的大小和可见性。
- requirement 选择卡片与普通课程卡片的对齐方式得到统一。
- communication 等组合 requirement 改为更清晰的课程卡片格式。
- additional major 的身份颜色与 workload 颜色分开表达，避免视觉重叠。
- 在课程计划前加入使用指南，解释：
  - 课程可以拖动。
  - 不同颜色代表的 requirement 来源。
  - workload 标签的含义。
  - prerequisite 或学期限制错误如何处理。

### GenEd

- GenEd 从静态数字改为按 category 计算的进度。
- 用户选择一项有效 GenEd 后，进度实时增加。
- 界面区分 AND 与 OR：
  - AND 表示所有 category 都必须完成。
  - OR 表示在一个 category 内选择一个合格课程即可。
- GenEd elective 已接入真实课程候选，而不是无法操作的空槽位。

## 四、路径生成和校验修复

### 学期与移动规则

- 增加课程最低年级和 semester placement 校验。
- 用户把课程移动到不满足 prerequisite 或年级限制的学期时，会显示错误提示。
- 错误弹窗可以通过 OK 正常关闭。
- 被拒绝的移动会回滚，不再留下错误的课程状态。
- 修复“移动 Humanities 却错误提示正在移动 15-251”的 stale drag state 问题。
- 修复 Sophomore Spring 错误地只能显示三门课程的问题。

### Prerequisite

- prerequisite 校验区分：
  - 已验证的 prerequisite。
  - 当前数据库缺少 prerequisite 信息。
  - 因学期顺序而暂时无法满足的 prerequisite。
- 增加部分可靠的课程完成推导，例如完成高阶课程时，可以推导已经满足必要的低阶课程或 placement requirement。
- 未完整导入 prerequisite 的课程会给出明确的数据状态提示，而不会伪装成已经完全验证。

### Degree audit 语义

- 区分“已经排入未来计划”和“学生已经学术完成”。
- 不再把未来计划中的课程错误计为 completed。
- primary degree 和目标专业分别计算进度。
- 路径结果现在分别显示：
  - 当前本科专业还剩多少 requirement。
  - additional major、minor 或 transfer target 还剩多少 requirement。
- 对不可能在目标时间前完成的路径增加结构化 warning。

## 五、Major、Additional Major 和 Minor 数据

### Current Major 已完成真实 audit 的专业

目前以下五个 current major 可以通过 **Explore my current major** 进入真实 requirement 选择和路径生成：

1. Statistics and Machine Learning
2. Mechanical Engineering
3. Computer Science
4. Electrical and Computer Engineering
5. Information Systems

对于尚未完成验证的 current major，系统会明确显示数据仍在审核，不会生成看似完整的虚假课程计划。

### 本次补齐的三个热门 Current Major

#### Computer Science B.S.

补充了：

- CS core。
- Mathematical foundations。
- Linear algebra。
- Multivariable calculus。
- Probability。
- Artificial Intelligence elective。
- Domains elective。
- Logic and Languages elective。
- Software Systems elective。
- 两门 SCS electives。
- Technical Communication。
- 360-unit degree minimum。

同时修复了自动抽取把整张 CS 课程表误判成“9 选 9”的问题。

#### Electrical and Computer Engineering B.S.

补充了：

- CIT 与 ECE 固定技术课程。
- 第二门 introductory engineering course。
- Probability。
- Mathematical concepts and proofs。
- Math/science electives。
- ECE foundation courses。
- ECE breadth and coverage electives。
- Advanced ECE electives。
- ECE capstone。
- 379-unit degree minimum。

ECE Academic Guide 才能最终决定的课程替代和分类不会被系统自动假定为批准。

#### Information Systems B.S.

补充了：

- IS core。
- Mathematics。
- Programming foundation。
- Data structures。
- HCI core。
- Professional Communications。
- Quantitative Analysis and Research Methods。
- Innovation and Entrepreneurship。
- IS concentration。
- 360-unit degree minimum。

同时修复了自动抽取把 programming sequence 错误解释为“4 门全部完成”的问题。

### 当前可作为规划目标的范围

- 10 个热门 primary/transfer major。
- 6 个 additional major。
- 8 个 minor。

本次新增或完善的 profile 包括：

- ECE internal transfer。
- Information Systems internal transfer。
- Computer Science and Arts transfer。
- Economics additional major。
- Business Administration minor。
- Machine Learning minor。
- StatML 和 MechE 的 current-major/internal-transfer 复用逻辑。

此外，对明确不适用的组合加入限制。例如，SCS 学生选择 Machine Learning minor 时，会得到明确提示，因为该项目面向 SCS 以外的学生。

## 六、Elective 系统

- 新增 current-major elective、goal-program elective 和 GenEd elective 的后端查询范围。
- elective picker 使用当前课程数据库里的真实课程、units、开课学期和 section 数量。
- 自动排除研究生课程。
- StatML、CS、ECE、IS、MechE 和 BCSA 使用各自对应的课程前缀提供建议。
- requirement 中的 `xx` 类型课程范围会展开为真实候选课程。
- 修复有效 requirement 课程存在于目录中、却没有被加载到规划图的问题。

## 七、Explore My Current Major

`Explore my current major` 已从只支持 StatML 的特殊入口，改成通用流程：

1. 根据用户选择的 current major 请求真实 primary-major profile。
2. 如果数据已验证，进入 Requirement Choice 页面。
3. 用户完成选择后生成 current-major plan。
4. 如果数据未验证，显示清楚的数据审核状态，且不会偷偷使用占位计划。

已在浏览器中实际验证 Information Systems：

- 能从 Step 2 选择 Explore my current major。
- 能进入 Finish your course choices。
- 正确显示 11 个待决定项目。
- Choose now、Decide later、进度条和继续生成计划按钮正常显示。

## 八、20 个现实组合回归测试

新增一套产品级现实场景测试，覆盖不同学院、转专业、additional major、minor、课程重叠、学期容量和资格限制。

重点场景包括：

- CFA Architecture 转 BXA。
- Mechanical Engineering 加 CS/AI 类 additional major。
- StatML 转 Information Systems。
- StatML 转 ECE。
- StatML 转 CS。
- 不同 SCS additional major 与 minor。
- 目标完成时间无法实现的情况。
- primary-major 与目标专业课程重叠但不能错误重复计入的情况。

这些测试不只检查接口是否返回 200，还检查：

- 是否生成学期路径。
- requirement 是否真实进入路径。
- 每学期是否超过 unit limit。
- primary major 是否被正确保留或替换。
- overlap 与 double counting 是否被分别处理。
- 未完成课程是否没有被误标为 completed。
- 不符合资格的组合是否返回明确错误。

## 九、测试与运行结果

当前自动测试结果：

- **82 个测试全部通过。**
- 20 个现实场景中的子检查全部通过。
- JSON 数据格式检查通过。
- Git diff whitespace 检查通过。
- CS、ECE、IS 三个 current-major planner 均能生成路径。
- 三个专业生成的课程没有重复课程 ID。
- 生成的 semester 没有超过配置的 unit limit。
- 数据库连接未关闭的测试警告已经修复。

当前本地网站运行地址：

<http://127.0.0.1:8000>

## 十、今天修改的主要文件

- `Backend/application.py`
  - Program directory、elective API、profile 接入、资格限制、规划 warning 和课程数据加载。
- `Data/processed/requirements.json`
  - StatML、MechE、CS、ECE、IS 等真实 current-major requirements。
- `Data/processed/program_profiles.json`
  - Transfer、additional major 和 minor profiles。
- `Data/processed/program_directory.json`
  - 项目目录与真实 planning profile 的映射。
- `Engine/degree_audit.py`
  - Primary degree 与 selected goal 的独立 audit。
- `static/app.js`
  - Requirement Choice、Explore current major、GenEd progress、Plan 交互和错误处理。
- `static/index.html`
  - 新页面结构和控件。
- `static/style.css`
  - Requirement 行、audit、课程卡片、进度和响应式布局。
- `tests/test_planning.py`
  - 新功能与数据可靠性测试。
- `tests/test_realistic_scenarios.py`
  - 20 个现实学生组合的产品级回归测试。

## 十一、当前限制与下一步

目前还不能称为“所有 CMU major/minor 都达到 Stellic 完整度”。当前策略是只对经过核对的数据标记为 planning ready，而不是为了扩大数量自动发布不可靠的课程规则。

建议下一阶段按以下顺序继续：

1. 补全 Economics、Business Administration、Architecture 等热门 current-major audit。
2. 扩充 Engineering、Dietrich、MCS 和 CFA 的热门 minor/additional major。
3. 导入更完整的官方 prerequisite 数据，并区分 prerequisite、corequisite 和 placement。
4. 加入 requirement 课程双重计数上限的逐课程 audit。
5. 为每个 catalog year 保存独立规则，避免新旧年级要求混用。
6. 增加与 Stellic 人工样本逐项对照的 golden test。

## 十二、总结

今天最大的进展不是增加了几个页面，而是让 major requirement、用户选择、课程路径和 degree audit 开始使用同一套真实状态。系统现在能够明确区分：什么已经完成、什么已经排入计划、什么需要用户选择、什么数据还没有经过验证。这使后续扩展更多专业时，可以复用同一套结构和测试，而不需要为每个专业重新制作一个静态界面。
