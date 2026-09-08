# RepoFrame

基于仓库本地文件的 AI 开发控制面。Agent 负责写代码，RepoFrame 管理工作所需的产品信息、开发模式和按需启用的复杂任务目标。

## 开始使用

需要 Node.js 24 或更新版本。当前为 `restart` 分支的本地开发版本，尚未发布到 npm；请先从源码安装，避免 `npx repoframe` 下载到其他版本。

```powershell
npm install
npm run build
npm pack
```

在目标仓库运行已构建的 CLI：

```powershell
node F:/projects/RepoFrame/dist/cli.js init
node F:/projects/RepoFrame/dist/cli.js
```

也可以将生成的 `repoframe-0.4.0.tgz` 安装到指定工具目录，再调用它的可执行文件。包发布后，对应入口为 `npx repoframe init` 和 `npx repoframe`。

默认操作当前目录，监听 `http://127.0.0.1:7331` 并打开浏览器。指定目录、端口或关闭自动打开：

```powershell
node F:/projects/RepoFrame/dist/cli.js --repo F:/projects/RepoFrame/_test/260908 --port 7331 --no-open
```

## 初始化：先准备，再确认

1. 在目标仓库提供 `PRD.md`。
2. 运行 `repoframe init`，准备 `.agents/`、初始状态、薄的 `AGENTS.md` 和初始化 Skill。
3. 把 CLI 输出的中文指令交给现有 Coding Agent。
4. Agent 按 `.agents/skills/repoframe-init/SKILL.md` 提炼产品信息，展示结果并经你确认后写入 `.agents/docs/product.json`。

CLI 不调用模型，不生成产品事实，也不创建示例目标。没有产品信息时 UI 会显示初始化待完成提示。重复初始化保留已有内容，已有 `AGENTS.md` 仅追加一次 RepoFrame 路由。

## 日常工作模式

左侧导航提供「快速开始」「项目」「目标」。快速开始并排展示开发模式和当前目标，没有目标时也保留框架。顶部的「正常开发 / 小步迭代」开关在所有页面可用；本地连接状态显示在左下路径上方。

| 模式                 | 作用                                   | 当前目标             |
| -------------------- | -------------------------------------- | -------------------- |
| 正常开发 `default`   | 按用户请求开发，选择必要验证           | 可为空，也可按需启用 |
| 小步迭代 `iteration` | 最小必要修改、针对性验证、避免无关重构 | 必须为空             |

没有目标是日常状态。普通代码请求不自动创建目标。迭代模式缩小验证范围，不跳过必要验证。

## 复杂任务目标

目标仅用于需要跨多次执行恢复的复杂任务。目标本身不会启动 Agent，也不是第三种工作模式。

- **创建**只保存文件；**创建并启用**会进入正常开发并设置当前目标。
- **启用**已有目标，同样进入正常开发；前一个目标的进展保留。
- 存在当前目标时，UI 和 API 都拒绝切换到小步迭代。
- **暂停**清除当前引用，保留文件、进展和未完成状态，模式保持正常开发。之后可手动进入迭代。
- **完成**保留目标文件并标记已完成，清除对应当前引用。
- **重新启用**可恢复未完成目标，也可将已完成目标重新打开。

启用后，把“请读取 AGENTS.md，继续推进当前目标……”的指令交给现有 Agent。Agent 可记录真实进展，有充分完成依据后完成目标；不自行改写产品规则或目标定义。

## 文件协议

```text
PRD.md
AGENTS.md
.agents/
  state.json
  docs/product.json
  goals/<goal-id>.json
  skills/repoframe-init/SKILL.md
```

常驻状态：

```json
{ "mode": "default", "activeGoal": null }
```

产品信息：

```json
{
  "summary": "产品描述",
  "users": "主要用户",
  "coreRequirements": ["核心需求"],
  "constraints": [],
  "nonGoals": []
}
```

按需创建的目标：

```json
{
  "title": "邮箱认证",
  "objective": "完成邮箱密码登录流程",
  "doneWhen": ["可以登录", "受保护路由正常工作"],
  "constraints": [],
  "progress": [],
  "status": "open"
}
```

目标文件名就是 ID，支持小写字母、数字、连字符和下划线，长度不超过 80，排除系统保留名称。修改标题不修改 ID。旧目标没有 `status` 时按 `open` 读取。

外部 Agent 可直接编辑 JSON，文件监听会让 UI 刷新。未知扩展字段在受支持编辑中保留。损坏 JSON、失效引用或 `iteration + activeGoal` 会显示诊断，不静默修复；非法组合需要先手工修正状态文件。目标已经不存在时，可显式暂停失效的当前引用。

## 编辑与本地服务

产品信息只能通过明确的编辑操作保存，正常 Agent 工作不主动修改。编辑中的草稿不被外部更新覆盖；保存检查文件版本，冲突时保留草稿并要求重新加载。

项目页按 `product.json` 的实际字段动态显示。五个基础字段使用中文标题，新增字段直接以字段名显示。点击「增加字段」，填写名称并添加到表单后输入内容；新字段默认为字符串，无需选择类型，点击「保存产品信息」后写入文件。已有字符串列表逐项编辑，数字、布尔值、对象及混合数组以 JSON 编辑并保留类型。五个基础字段的校验仍然保留，扩展字段不会因编辑基础信息而丢失。

写入使用同目录临时文件替换，并在服务内串行处理。多文件操作不是数据库事务；若中途失败，页面会重新读取文件并报告实际状态。外部编辑器不受服务锁控制，版本检查无法消除最终替换瞬间的全部竞争窗口。无需额外数据库或操作日志。

服务只监听本机，检查 Host 和写入来源，拒绝越界路径与符号链接。没有任意文件编辑、shell、Git 操作、云端账户、调度器、Agent 运行器或遥测。

## 开发和验证

```powershell
npm run typecheck
npm test
npm run build
npm run test:e2e
```

端到端测试需要 Playwright Chromium。若不希望缓存和临时下载使用系统盘，可在 PowerShell 中设置以下环境变量；这也是本次开发所用配置：

```powershell
$env:TEMP = 'D:/CodexHome/tmp/repoframe'
$env:TMP = $env:TEMP
$env:npm_config_cache = 'D:/CodexHome/cache/npm'
$env:PLAYWRIGHT_BROWSERS_PATH = 'D:/CodexHome/cache/playwright'
npx playwright install chromium
```

运行前创建这些目录。项目内 `node_modules/` 和构建产物留在项目所在磁盘。端到端测试使用 `.tmp/` 下的独立模拟仓库，截图保存在 `test-results/`。

开发 UI 时，先启动已构建的本地服务，再运行 `npm run dev`。Vite 将 `/api` 请求代理至本地服务；生产包直接提供静态页面，不需要 Vite。
