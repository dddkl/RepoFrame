<!-- repoframe:start -->

## RepoFrame 开发入口

开始工作前读取 `.agents/state.json` 和 `.agents/docs/product.json`。产品信息缺失时，读取 `.agents/skills/repoframe-init/SKILL.md`，从 `PRD.md` 提炼并经用户确认后初始化。

- `default`：按用户请求正常开发，按任务选择必要验证。
- `iteration`：优先最小改动与针对性验证，避免无关重构和不必要的全仓库检查；不得跳过必要验证。
- 两种模式常驻；复杂任务目标仅按需启用，不从普通请求自动创建或启用目标。
- 只有 `default` 允许非空 `activeGoal`。有当前目标时，先暂停或完成目标才能切换至 `iteration`；遇到冲突状态先报告，不继续执行目标。
- `activeGoal` 非空时读取 `.agents/goals/<activeGoal>.json`，根据用户指令及已记录进展推进。缺失、无效或已完成的目标应先报告。
- 产品和目标文件的字段值统一使用字符串；内容以 Markdown 编写，列表也写在字符串中。可据实际工作更新 `progress`；`doneWhen` 中所有条件均有实际依据后，清除对应 `activeGoal` 并将目标 `status` 设为 `completed`，保留目标文件。暂停只清除 `activeGoal`，保留 `open` 和进展，模式保持 `default`。
- 未经用户明确要求，不修改产品信息、目标目的、完成条件或约束。不自行启动调度器或循环运行 Agent。

<!-- repoframe:end -->
