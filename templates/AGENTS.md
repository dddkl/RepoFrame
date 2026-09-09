<!-- repoframe:start -->

# RepoFrame 开发入口

## 1. 读取上下文

开始工作时依次读取：
1. `.agents/state.json`：确认开发模式和 Active Goal。
2. `.agents/docs/product.md`：了解稳定产品信息；缺失时读取 `.agents/skills/repoframe-init/SKILL.md`，从 PRD.md 提炼并经用户确认后初始化。
3. 本文件下方的用户约定。
4. `.agents/docs/index.json`：根据 description 按需读取相关文档；任务范围变化时补读，可能相关但描述不足时读取正文确认。索引缺失或无效时报告。

本入口直接引用的规范文档不登记到 index.json，也不在文档视图展示。类别只用于整理，不决定规则优先级。

## 2. 工作模式

- `default`：按用户请求开发，选择必要验证。
- `iteration`：最小必要改动与针对性验证，避免无关重构和不必要的全仓库检查，不跳过必要验证。
- 两种模式常驻，复杂目标仅按需启用，不从普通请求自动创建或启用目标。

## 3. 目标处理

- 只有 default 允许非空 activeGoal；状态冲突时先报告，不继续执行目标。
- activeGoal 非空时读取 `.agents/goals/<activeGoal>.json`，按用户指令继续；目标缺失、无效或已完成时先报告。
- 执行、恢复目标或修改进展前，读取 `.agents/docs/repoframe-goal-progress.md` 并遵守其中的结构和维护规范；仅查看目标不修改进展。
- 目标内容字段为 Markdown 字符串，progress 为结构化路径。完成条件全部有实际依据后，清除对应 activeGoal 并标记 completed，保留目标文件。暂停只清除 activeGoal，保留 open 和进展，模式保持 default。
- 有当前目标时，先暂停或完成它，再切换到 iteration。

## 4. 修改边界

未经用户明确要求，不修改稳定产品信息、目标目的、完成条件或约束；不自行启动调度器或循环运行 Agent。固定入口由 RepoFrame 维护，用户补充写入下面的用户约定区域。

<!-- repoframe:end -->

## 用户约定
<!-- repoframe:user:start -->

<!-- repoframe:user:end -->
