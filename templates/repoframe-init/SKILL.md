---
name: repoframe-init
description: 从仓库已有 PRD 提炼稳定产品信息，经用户确认后写入 RepoFrame 产品 Markdown。用于首次初始化或用户明确要求重新整理产品信息，不用于日常代码修改或目标执行。
---

# 初始化 RepoFrame

读取仓库根目录 `PRD.md`，以及与产品定位直接相关的已有材料。缺少 PRD 时请用户提供需求材料；模板占位符不算已知事实。优先提炼已有信息，不自行增加工程规范或技术约束。

将稳定产品信息整理为 `.agents/docs/product.md` 的完整 Markdown 正文。根据实际内容选择标题、段落或列表，不预设字段，不要求固定章节，不使用 JSON 包装内容。项目页展示渲染结果，编辑页显示原文。

展示具体提炼结果，只对材料不能确定的必要信息提问。获得用户对这份结果的一次确认后再写入；已有针对同一结果的明确确认无需重复询问。调用本 Skill 本身不表示用户确认了尚未展示的内容。

需要目录和入口时运行 `npx repoframe init`。写文件前重新读取已有产品文档，保留无关内容；除用户明确要求外，不覆盖已确认的信息。以 UTF-8 保存，先写同目录临时文件再替换；若文件期间变化则停止覆盖并报告。

检查 `AGENTS.md` 引用 `.agents/state.json`、`.agents/docs/product.md`、`.agents/docs/index.json` 和目标目录。产品文档不登记到文档索引。初始化默认状态为 `{"mode":"default","activeGoal":null}`，不得重置已有状态，不创建示例目标，不修改原始 PRD。

完成后说明已写入的产品信息，并提示运行 `npx repoframe` 打开工作台。本 Skill 不调用特定 Agent SDK、模型 API 或调度系统。
