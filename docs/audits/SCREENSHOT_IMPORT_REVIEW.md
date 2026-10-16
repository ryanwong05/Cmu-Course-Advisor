# CMU Course Advisor — Screenshot / Academic History Import Review

> 审计日期：2026-10-15。结论基于当前代码、现有测试和一次本地 text-PDF sanity check；没有把未运行的 vision model 说成已验证成功。

## 结论

这项功能不是从零开始，已经达到 **partial implementation**：支持 PDF/PNG/JPG 多文件、提取结果 review、人工增删改、显式 Confirm & Import，以及 merge 到 Student State。设计方向正确，尤其是“模型只读事实、不判断学术政策”和“先确认再导入”。

但它还不能作为公开 MVP 的默认承诺：文本 PDF 路径可用；图片/扫描 PDF 依赖本地 Ollama `qwen2.5vl:3b`，当前审计机器的 Ollama 服务未运行；没有浏览器 E2E 或真实匿名样本集；upload 也缺 request-level 总量限制。

## 当前实现

### 支持输入

- `application/pdf`
- `image/png`
- `image/jpeg`
- 前端可一次选择多个文件。
- 后端对每个文件限制 10 MB，并用 magic bytes 检测真实类型；图片使用 Pillow verify。

代码位置：`Backend/academic_history_import.py:20-93`、`Backend/application.py:1968-2028`。

### Extraction strategy

```text
文件
  ├─ text-based PDF → pypdf native text → deterministic regex parser
  ├─ scanned PDF → 最多 12 页渲染为 PNG → local Ollama vision
  └─ PNG/JPG → local Ollama vision
        ↓
normalize + catalog lookup + status/term/year validation + dedupe
        ↓
review UI（用户可修改/删除/补充）
        ↓
Confirm & Import
        ↓
merge into completed / in-progress / planned Student State
```

图片默认模型：`qwen2.5vl:3b`；endpoint 为本机 `127.0.0.1:11434`，temperature 0，要求 JSON。原始图片 bytes 不写入项目数据库。

### 安全边界

- extractor prompt 明确只抽 course facts，不推断 requirement，也不需要学生身份。
- 只有 catalog 中可确认的 course ID 才能变成 canonical course。
- invalid/ambiguous rows 带 issues/warnings，用户 review 后才 merge。
- completed、in_progress、planned 分开处理。
- merge 逻辑去重，不应覆盖 unrelated Student State。

这是正确的产品边界：OCR/vision 可以帮助录入，不能替代 deterministic degree audit。

## 实际验证结果

### Confirmed working

- 173 个项目测试全部通过，其中包含 import validation、normalization、merge 与 mocked extractor 分支。
- 本轮对合成 text PDF 的 sanity check 能读出课程并进入 catalog validation。
- API 和前端都存在 review/confirm 阶段；没有静默把 OCR 结果当成 completed。
- completed-course merge 进入统一 Student State 后，Linguistics → CS fixture 不会重复安排 21-127、15-122 或多余 15-112。

### Not verified end-to-end

- 当前 `127.0.0.1:11434` 连接失败，因此 PNG/JPG 和 scanned PDF 的 vision extraction **当前不可用**。
- 没有实际 SIO 截图/扫描件的匿名 golden dataset。
- 没有 browser automation 覆盖“选择文件 → review → 修改 → confirm → planner”的完整流程。
- 测试主要依靠 mock extractor，不能证明模型对模糊截图、多页、裁剪、表格和重复课程的准确率。

### Probable issue

曾在合成 PDF 输出中观察到 `B+` 可能被读成 `B`。parser regex 本身允许 `+/-`，所以更可能是 PDF text extraction 的字符布局问题。没有可保存的最小 fixture 前，应标记为 probable，而不是 confirmed bug。

## UX review

### 已做对

- Course history 是 optional refinement，不阻塞先生成起始计划。
- 提取结果在导入前可读、可编辑、可删除。
- 低置信度/未知课程不会自动成为正式完成记录。
- 导入后与手工勾选走同一 Student State 概念。

### MVP 前应改

1. 上传区域先显示 capability：Text PDF available / Image extraction unavailable，避免用户上传后才失败。
2. review row 明确展示：原始文本、normalized course、term、status、grade、confidence、warning。
3. 对 unknown course 提供“保留为待确认”而不是猜测最接近 course。
4. 同一 course 跨文件重复时显示 merge reason。
5. Confirm 后显示具体变更：新增 completed N、in-progress N、planned N、跳过 N。
6. 提供 Undo import，至少在当前 session 内可回滚。
7. 对成绩、姓名、学号等敏感信息说明：哪些送入本地模型、是否保留、何时清除。

## Security / privacy review

### 当前优点

- vision 默认走 localhost，不上传 OpenAI。
- transfer advisor 的云端 fallback 与 academic-history import 是分开的。
- 原始文件没有持久化逻辑。
- MIME sniff 和 image verification 减少伪装文件风险。

### 必须补的 safeguards

- **批次限制：** 当前仅每文件 10 MB；应限制文件数量、总 bytes、总 PDF pages 与总 vision calls。
- **解析资源限制：** PDF/page dimensions、decompression bomb、极大图片像素应有上限。
- **日志：** 不要记录 base64、原始 OCR 文本、姓名/学号；错误日志只留 request ID 和安全原因码。
- **生命周期：** 明确 request 结束后 bytes/临时 render 不保留；若未来缓存，必须 opt-in、短 TTL、加密、可删除。
- **CSRF/rate limiting/deployment:** 若从 localhost 变成公网，必须加 origin/rate controls；当前本地原型假设不够。

## 推荐技术方案

维持当前“两级提取”，不要把所有文件都交给云端大模型：

1. 优先 native PDF text。
2. 对 text 做 deterministic CMU course-ID extraction。
3. 只有无文本/低覆盖页面才调用 local vision。
4. 所有模型输出都经过 schema + catalog validation。
5. 用户确认后才 merge。
6. Requirement satisfaction 始终由现有 deterministic engine 计算。

如果未来必须支持 hosted OCR，建议把 provider 放在现有 `AcademicHistoryExtractor` interface 后面，并默认关闭；不得将政策判断写进 prompt。

## 数据模型建议（最小扩展）

不要只存一串 completed IDs。MVP 可增加一个兼容性的 `academic_history_records` 层：

```json
{
  "course_id": "15-122",
  "status": "completed",
  "term": "fall",
  "year": 2026,
  "grade": "B+",
  "source_type": "uploaded_document",
  "source_filename": "redacted-display-name.pdf",
  "confidence": 0.92,
  "confirmed_by_user": true
}
```

Planner 仍接收兼容的 `completed_courses` projection；这样不破坏 API，又能支持 provenance、修正和 undo。文件名是否存储应允许关闭，且不得存原文件内容。

## Acceptance criteria

- text PDF、PNG、JPG、scanned PDF 各至少 10 个匿名 golden fixtures。
- course ID precision ≥ 99%；任何低置信度项都不得静默导入。
- status/term/grade 单独报告准确率；grade 不参与规划时也不能假装可靠。
- batch limits 在读取/推理前生效。
- Ollama/model 不可用时，UI 立即给出可行动的降级方案。
- confirm 前 Student State 完全不变；cancel 后无残留。
- confirm 后每条记录可追踪、可撤销，planner 不重复已完成课程。
- 原始文件不进入日志或长期存储。

## 工作量与优先级

因为核心流程已经存在，达到“受控 pilot 可用”约需 **2–4 个工程日**：aggregate limits、capability check、README/setup、golden fixtures、端到端 browser test、import summary/undo。达到“公开可靠”还需要真实匿名样本评测和部署安全工作。

优先级建议为 **P1**：先修完 planner correctness P0，再硬化 import。它是明显的 usability value-add，但不应抢在路径正确性之前。
