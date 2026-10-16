# CMU Course Advisor — Project Status Audit

> 审计日期：2026-10-15；实现状态更新：2026-10-16。对象为当前工作区实际代码，而不是 README 或历史对话中的目标状态。

## 一句话结论

项目已经是一个可运行、测试较充分的 **CMU 课程路径原型**，而不是空壳：它能处理 Student State、Dietrich GenEd、若干主修/转系/additional major/minor、先修课检查、学期容量、路径比较、解释性推荐和学业记录导入。但它距离可公开使用的 MVP 仍有三道门槛：**真实可规划项目覆盖率只有 9.9%，先修与政策数据仍不完整，浏览器中的手动编辑没有形成可持久化、可重新审计的 canonical plan state。**

## 仓库与运行状态

- Git 分支：`main`。
- 工作树在审计开始时为 clean。
- Git 显示 `main...origin/main [gone]`：本地分支仍引用一个已不存在的 upstream，需要在下次提交前修复 remote tracking。
- 最近提交：`6f09d3a Week 5 Commit 2 - feat: import academic history from SIO documents`。
- 没有发现 CI workflow，也没有根目录 LICENSE。
- Python 运行环境在 `venv/`，但 `requirements.txt` 没有列出测试依赖。

### 实际执行的测试

```text
venv/bin/python -m unittest discover -s tests -v
Ran 173 tests in 17.452s
OK
```

尝试过但未成功的命令：

```text
venv/bin/python -m pytest -q
No module named pytest
```

因此不能声称 pytest 通过；当前仓库的真实测试入口是 `unittest`。173 个测试通过证明现有回归面较好，但不等价于 213 个项目都可用，尤其没有浏览器 E2E 测试。

## 当前架构

### Frontend

- Vanilla HTML/CSS/JavaScript：`static/index.html`、`static/style.css`、`static/app.js`。
- `static/app.js` 约 4,586 行，承担页面导航、Student State、课程选择、API 请求、结果渲染、拖拽、GenEd 选择、比较、保存路径和导入 review；它仍是前端 god file。
- `static/course-selection.js`、`static/goals.js`、`static/program-explorer.js`、`static/results.js` 均为 0 字节的已跟踪文件。`app.js:4472-4586` 仍保留一份过期的“未来拆分清单”，说明拆分尚未发生。
- 保存路径仅使用 `localStorage`（`static/app.js:129-283`），没有用户账户或后端 persistence。

### Backend/API

- FastAPI 应用入口：`app.py` → `Backend/application.py`。
- `Backend/application.py` 约 2,060 行，包含 app setup、Pydantic models、directory/profile/baseline/plan/comparison/recommendation/advisor/import API，以及大量 orchestration；已比早期更模块化，但仍偏大。
- 已抽离的主要模块：
  - `Backend/requirements.py`：requirement option、named sets、curriculum/profile resolution。
  - `Backend/course_metrics.py`：FCE/placeholder workload metrics。
  - `Backend/course_recommendation.py`：确定性候选排序与过滤。
  - `Backend/path_comparison.py`：已生成路径间的确定性比较。
  - `Backend/academic_history_import.py`：PDF/image extraction、normalization、validation、merge。
  - `Backend/transfer_advisor.py`：Ollama/OpenAI 解释层。

### Planning/Requirement Engine

- `Engine/planning.py`：semester generation、capacity、program slots、未排诊断、多路径 pacing。
- `Engine/availability.py`：先修表达式与 offering/year eligibility。
- `Engine/student_state.py`：completed/in-progress/planned/locked semesters 的统一 state。
- `Engine/degree_audit.py`：primary degree 与 selected goal 的 audit summary。
- `Engine/baseline.py`：college baseline/GenEd；当前直接读取 `Data/scraped/scraped_college_requirements.json`。

### Data 与 ingestion

- `Data/processed/program_directory.json`：213 个 catalog program forms。
- `Data/processed/program_curriculum_registry.json`：193 个唯一 curriculum pages 的结构化 extraction。
- `Data/processed/requirements.json` 与 `program_profiles.json`：实际进入 planner 的 curated/verified subset。
- `Data/policies/`：transfer、elective、named course sets、aliases、sources、recommendation 等规则。
- `Data/processed/courses.sqlite`：课程、section、term、部分 FCE/元数据。
- `Scripts/data_pipeline/`：catalog/program/schedule/FCE 抓取、转换、审计脚本。

## 实际数据流

原始设想基本正确，但有两个重要修正：import 先进入确认层；结果页的手动编辑目前主要停留在 DOM，而非重新进入后端 planner。

```text
学生 profile / goal / 可选 PDF 或截图
    ↓
Frontend appState
    ├─ 文件 → /api/academic-history/extract → review → /merge → appState
    └─ 手工 completed / requirement choices
    ↓
/api/baseline + /api/plan
    ↓
derive_academic_state()
    ↓
curated requirements + program profile + college baseline
    ↓
Engine.generate_multiple_paths()
    ↓
degree audit + warnings + course catalog projection
    ↓
Frontend results / comparison / local DOM edits
    ↓
localStorage snapshot（不是后端 canonical plan）
```

## 已实现并可用的功能

- 学生当前 college、major、year/term、completed/in-progress/planned courses。
- 当前主修、内部转系、additional major、minor 四种 goal schema。
- 目标完成年、全局和逐学期 unit limits。
- Dietrich 14 类、115 units 的 GenEd baseline；completed requirement ID 与 course-based satisfaction。
- verified subset 的 semester-by-semester generation。
- completed-course implications；实测 Linguistics → CS 且完成 21-127/15-122 时不会重复安排三门课程。
- requirement-choice default、用户换课、添加 elective、拖动课程，以及本地的 prerequisite/offering/year/unit 检查。
- degree audit、未排 requirement 原因、eligibility/prerequisite warnings。
- deterministic path comparison 与 course recommendation。
- PDF、PNG、JPG 多文件导入 UI、确认/编辑、merge。
- local Ollama / optional OpenAI transfer-plan explanation；LLM 只解释 verified planner JSON，不负责算要求。

## 部分实现或不可靠的功能

| 能力 | 状态 | 证据/限制 |
|---|---|---|
| 当前主修 planning | 部分偏强 | 7 个 entry-specific primary flows 均在代表场景完整；其余绝大多数 CMU 主修仍只有目录/结构化数据。 |
| Internal transfer | 部分偏强 | 10 个目标可执行，9 个代表场景完整；BCSA post-transfer path 不完整。 |
| Additional major | 部分 | 6 个可执行，只有 HCI、Robotics 在统一代表场景完整。 |
| Minor | 部分偏强 | 8 个可执行，7 个完整；CB minor 候选不足。 |
| Degree fulfillment | 部分 | verified subset 内一致；绝大多数 CMU 项目没有被 promotion 到 planner。 |
| Workload-aware planning | 不可靠 | 有强度限制和第二路径，但 metrics 大量是 placeholder/fallback；“lower workload” 实测可出现 52 units 和较高 workload。 |
| Manual editing | 部分 | replace/move/add 可用并做本地校验；没有明确 remove fixed-course 流程，修改不会被后端重新生成和重新 audit。 |
| Saved plans | 部分 | 仅当前浏览器 localStorage，无跨设备、版本、账户或 server persistence。 |
| AP/IB/transfer credit | 部分 | API 返回 direct-equivalency metadata，但 StudentState 没有独立 credit provenance/model；用户最终仍按 completed course 处理。 |
| Screenshot import | 部分 | 流程和代码完整，但当前机器没有运行 Ollama vision service/model，图片端到端不可用；文本 PDF 可用。 |
| Undecided exploration | 部分 | 可浏览 directory，但没有兴趣/偏好推荐、flexibility plan 或“适合我”的解释。 |

## 缺失功能

- 大多数 majors/minors/additional majors 的 verified planner data。
- 一般化的 historical catalog-year ownership 与学生 catalog year。
- 后端 canonical plan mutation API、re-audit、undo/versioning。
- 持久化 Student State、账户、跨设备 saved plans。
- plan export（PDF/ICS/CSV/分享链接）。
- 完整 AP/IB/transfer-credit mapping 与来源状态。
- 前端 automated unit/E2E tests、CI gate。
- 大规模 course-offering forecast；目前 schedule 是当期证据，不是未来多年保证。

## 技术债与可疑代码

### 确认存在

1. **两个 god files**：`Backend/application.py` 与 `static/app.js`。先修 P0 bug 和 coverage 后再拆，不应在当前阶段做大重写。
2. **空模块**：四个 `static/*.js` 文件为 0 字节；要么真正迁移，要么删除，不能继续制造“已经模块化”的错觉。
3. **过期注释**：`static/app.js:4472-4586` 描述的若干“未来功能”实际上已经部分存在。
4. **前端硬编码 Stats/ML elective list**：`static/app.js:3295-3305`，与通用 program-data 目标冲突。
5. **默认 52 units**：Pydantic 与 UI 默认均为 52（`Backend/application.py:303-309`、`static/index.html:755`），虽然用户可以改、engine 支持逐学期 override，但它不是按 college/year 自动确定的官方政策。
6. **stale processed file**：`Data/processed/college_requirements.json` 六个 college 都是 placeholder，而 runtime 使用 `Data/scraped/scraped_college_requirements.json`。这不是当前 runtime 的重复 source of truth，但会误导维护者。
7. **placeholder workload data**：`Data/processed/course_metrics.json` 明确含 `stakeholder_placeholder`；不能以此做高可信度 workload advice。
8. **测试依赖未声明**：pytest 不存在，CI 不存在。

### 没有复现的历史问题

- 在 21 个可执行目录路径中，没有发现同一 course instance 被重复排入，也没有发现 `total_units > unit_limit`。
- Stats/ML 当前主修的 14 个 Dietrich GenEd slots 均被安排，planner 与 degree audit 都报告 0 unresolved。
- Experiential Learning 仍是独立 requirement slot，不再错误绑定 36-200；`Engine/baseline.py:65-72` 有防御性 normalization，对应 regression test 通过。
- 这些结论只覆盖当前代表场景，不代表所有手动编辑组合都经过 E2E 验证。

## API 与成本策略

- **确定性、不应交给 LLM：** requirements、prerequisites、completion implications、units、semester eligibility、degree audit、comparison metrics、recommendation filters。
- **本地 LLM：** transfer advice 默认使用 Ollama `qwen3:1.7b`；图片 extraction 默认 `qwen2.5vl:3b`。没有按次 API 成本，但有模型安装、内存和延迟成本。
- **云端 LLM：** 仅 transfer advice 在 Ollama 失败且配置 `OPENAI_API_KEY` 时使用 OpenAI Responses API；`store=false`。当前没有结果 cache，每次 Analyze Again 都可能重复调用。
- **可缓存：** 同一 plan hash 的 advisor explanation、同一 upload hash 的临时 extraction（若实施，应设短 TTL、加密且默认不持久化原图）。
- **ScottyLabs：** 适合在明确许可和稳定性评估后补充课程发现、section、评价/FCE 类元数据；不应取代 CMU 官方 curriculum/policy sources，也不应成为 deterministic policy engine 的唯一来源。

## Repository health

| 项目 | 评价 |
|---|---|
| Backend unit/integration tests | 良好：173/173 通过 |
| Frontend automated tests | 缺失 |
| CI | 缺失 |
| Dependency reproducibility | 一般：有版本范围，但缺 test dependencies/lockfile |
| Git remote tracking | 异常：`origin/main [gone]` |
| Data provenance | 有 source URLs/status，但 verified subset 较小 |
| Architecture | 后端已开始拆分；前端仍高度集中 |
| Security/privacy | 原图不保留、vision local-first；但 upload 缺总文件数/总大小限制 |

## 本地运行

```bash
cd "/Users/ryanwong/Desktop/Projects/AI Projects/AI CMU Course Development"
venv/bin/uvicorn app:app --host 127.0.0.1 --port 8000
```

打开 `http://127.0.0.1:8000`。

运行现有测试：

```bash
venv/bin/python -m unittest discover -s tests -v
```

启用免费本地 transfer advisor：

```bash
ollama serve
ollama pull qwen3:1.7b
```

启用图片/扫描 PDF 导入还需要默认 vision model：

```bash
ollama pull qwen2.5vl:3b
```

当前审计时本机 `127.0.0.1:11434` 未运行，因此不能把图片导入称为“当前可直接使用”。

## 建议的责任边界（不要求现在重写）

- `Backend/application.py`：models、routes、薄 orchestration。
- `Backend/*`：import、comparison、recommendation、advisor、policy lookup。
- `Engine/*`：纯确定性 planning/state/audit。
- `Data/processed`：machine-generated catalogs/registries。
- `Data/policies`：人工审核、带来源和 catalog year 的政策。
- `static/*`：逐步按 screens/state/api/rendering 拆分；先补浏览器测试再移动代码。

当前优先级不是继续“清理得更漂亮”，而是修复 planner 完整性、建立真实 coverage gate、补先修/政策数据和形成 canonical editable plan。
