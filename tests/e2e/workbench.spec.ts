import { test as base, expect } from "@playwright/test";
import { promises as fs } from "node:fs";
import path from "node:path";
import { spawn, execFileSync, type ChildProcess } from "node:child_process";
import { createServer } from "node:net";

const product = {
  summary: "一个离线优先的个人笔记工具，让想法、资料与写作有序沉淀。",
  users: "希望在本地管理知识的独立开发者与写作者",
  coreRequirements:
    "- 创建、编辑和检索 Markdown 笔记\n- 按标签整理内容，快速找到需要的资料\n- 所有内容保存在本地，支持导入和导出",
  constraints: "- 使用本地文件存储\n- 保持离线可用",
  nonGoals: "- 多人实时协作\n- 云端账户与同步",
};
const test = base.extend<{
  repo: { root: string; url: string; restart: () => Promise<void> };
}>({
  repo: async ({}, use) => {
    const baseDir = path.resolve(".tmp/e2e");
    await fs.mkdir(baseDir, { recursive: true });
    const parent = await fs.mkdtemp(path.join(baseDir, "run-"));
    const root = path.join(parent, "本地笔记");
    await fs.mkdir(root);
    execFileSync(
      process.execPath,
      [path.resolve("dist/cli.js"), "init", "--repo", root],
      { windowsHide: true },
    );
    await fs.writeFile(
      path.join(root, ".agents/docs/product.json"),
      JSON.stringify(product),
    );
    const probe = createServer();
    await new Promise<void>((resolve) => probe.listen(0, "127.0.0.1", resolve));
    const port = (probe.address() as { port: number }).port;
    await new Promise<void>((resolve) => probe.close(() => resolve()));
    const url = `http://127.0.0.1:${port}`;
    let processHandle: ChildProcess;
    const stop = async () => {
      if (!processHandle || processHandle.exitCode !== null) return;
      const exited = new Promise<void>((resolve) =>
        processHandle.once("exit", () => resolve()),
      );
      processHandle.kill();
      await exited;
    };
    const start = async () => {
      processHandle = spawn(
        process.execPath,
        [
          path.resolve("dist/cli.js"),
          "--repo",
          root,
          "--port",
          String(port),
          "--no-open",
        ],
        { windowsHide: true, stdio: "pipe" },
      );
      let output = "";
      processHandle.stdout?.on("data", (chunk) => {
        output += String(chunk);
      });
      processHandle.stderr?.on("data", (chunk) => {
        output += String(chunk);
      });
      await expect
        .poll(() => output, { timeout: 10000 })
        .toContain("RepoFrame 已启动");
    };
    await start();
    try {
      await use({
        root,
        url,
        restart: async () => {
          await stop();
          await start();
        },
      });
    } finally {
      await stop();
      await fs.rm(parent, { recursive: true, force: true });
    }
  },
});

test("常驻模式、按需目标、暂停恢复及重启持久化", async ({
  page,
  repo,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(repo.url);
  await expect(page.getByText("本地已连接")).toBeVisible();
  await expect(page.getByRole("heading", { name: "本地笔记" })).toBeVisible();
  await expect(
    page.getByRole("region", { name: "当前目标面板" }),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("项目概览.png"),
    fullPage: true,
  });
  await page
    .getByRole("region", { name: "开发模式面板" })
    .getByRole("button", { name: "小步迭代", exact: true })
    .click();
  await expect(
    page
      .getByRole("region", { name: "开发模式面板" })
      .getByRole("button", { name: "小步迭代", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "目标", exact: true }).click();
  await page
    .getByRole("button", { name: "创建目标", exact: true })
    .first()
    .click();
  await page.getByLabel("目标名称", { exact: true }).fill("实现全文检索");
  await page.getByLabel("目标标识（可选）").fill("search");
  await page
    .getByLabel("目标目的", { exact: true })
    .fill("让用户快速找到本地笔记");
  await page
    .getByLabel("完成条件", { exact: true })
    .fill("中文关键词能够返回正确结果");
  await page.getByRole("button", { name: "仅创建", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "实现全文检索" }),
  ).toBeVisible();
  expect(
    JSON.parse(
      await fs.readFile(path.join(repo.root, ".agents/state.json"), "utf8"),
    ),
  ).toEqual({ mode: "iteration", activeGoal: null });
  await page.getByRole("button", { name: "启用目标", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "暂停目标", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "快速开始", exact: true }).click();
  await expect(
    page
      .getByRole("region", { name: "开发模式面板" })
      .getByRole("button", { name: "小步迭代", exact: true }),
  ).toBeDisabled();
  await expect(
    page
      .getByRole("group", { name: "全局开发模式", exact: true })
      .getByRole("button", { name: "正常开发", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.screenshot({
    path: info.outputPath("快速开始-已启用目标.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "打开目标", exact: true }).click();
  const file = path.join(repo.root, ".agents/goals/search.json");
  const goal = JSON.parse(await fs.readFile(file, "utf8"));
  goal.progress = "已建立中文分词索引，并通过基础查询测试";
  await fs.writeFile(file, JSON.stringify(goal));
  await expect(page.getByText(goal.progress)).toBeVisible();
  await page.screenshot({
    path: info.outputPath("目标详情.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "暂停目标", exact: true }).click();
  await page.getByRole("button", { name: "快速开始", exact: true }).click();
  await expect(
    page
      .getByRole("region", { name: "开发模式面板" })
      .getByRole("button", { name: "小步迭代", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("region", { name: "开发模式面板" })
    .getByRole("button", { name: "小步迭代", exact: true })
    .click();
  await expect(
    page
      .getByRole("region", { name: "开发模式面板" })
      .getByRole("button", { name: "小步迭代", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await repo.restart();
  await page.reload();
  await expect(
    page
      .getByRole("region", { name: "开发模式面板" })
      .getByRole("button", { name: "小步迭代", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.goto(`${repo.url}/#goals/search`);
  await page.getByRole("button", { name: "启用目标", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "暂停目标", exact: true }),
  ).toBeEnabled();
  await expect(page.getByText(goal.progress)).toBeVisible();
  await page.getByRole("button", { name: "完成目标", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "重新启用", exact: true }),
  ).toBeVisible();
  expect(
    JSON.parse(
      await fs.readFile(path.join(repo.root, ".agents/state.json"), "utf8"),
    ),
  ).toEqual({ mode: "default", activeGoal: null });
  expect(JSON.parse(await fs.readFile(file, "utf8")).status).toBe("completed");
  expect(errors).toEqual([]);
});

test("产品编辑、外部冲突保护、重新加载与中文校验", async ({
  page,
  repo,
}, info) => {
  await page.goto(`${repo.url}/#project`);
  await expect(page.getByText("本地已连接")).toBeVisible();
  await page.getByRole("button", { name: "编辑产品信息" }).click();
  await page
    .getByRole("textbox", { name: "产品描述", exact: true })
    .fill("尚未保存的本地草稿");
  const file = path.join(repo.root, ".agents/docs/product.json");
  await fs.writeFile(
    file,
    JSON.stringify({ ...product, summary: "来自 Agent 的新描述" }),
  );
  await expect(page.getByText("文件在编辑期间发生变化")).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "产品描述", exact: true }),
  ).toHaveValue("尚未保存的本地草稿");
  await expect(
    page.getByRole("button", { name: "保存产品信息" }),
  ).toBeDisabled();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "重新加载", exact: true }).click();
  await expect(
    page.getByRole("textbox", { name: "产品描述", exact: true }),
  ).toHaveValue("来自 Agent 的新描述");
  await page.getByRole("textbox", { name: "产品描述", exact: true }).fill("");
  await page.getByRole("button", { name: "保存产品信息" }).click();
  await expect(
    page.getByRole("textbox", { name: "产品描述", exact: true }),
  ).toHaveAttribute("aria-invalid", "true");
  await page
    .getByRole("textbox", { name: "产品描述", exact: true })
    .fill("已确认的本地笔记工具");
  await page.screenshot({
    path: info.outputPath("产品编辑.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "保存产品信息" }).click();
  await expect(
    page.getByRole("dialog", { name: "编辑产品信息", exact: true }),
  ).toHaveCount(0);
  expect(JSON.parse(await fs.readFile(file, "utf8")).summary).toBe(
    "已确认的本地笔记工具",
  );
});

test("窄屏导航、创建并启用、离开草稿保护", async ({ page, repo }, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(repo.url);
  await expect(
    page
      .getByRole("group", { name: "全局开发模式", exact: true })
      .getByRole("button", { name: "正常开发", exact: true }),
  ).toBeEnabled();
  await page.screenshot({
    path: info.outputPath("窄屏项目.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "切换导航", exact: true }).click();
  await page.getByRole("button", { name: "目标", exact: true }).click();
  await page
    .getByRole("button", { name: "创建目标", exact: true })
    .first()
    .click();
  await page.getByLabel("目标名称", { exact: true }).fill("移动端编辑体验");
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.getByRole("button", { name: "取消", exact: true }).click();
  await expect(page.getByLabel("目标名称", { exact: true })).toHaveValue(
    "移动端编辑体验",
  );
  await page.getByLabel("目标目的", { exact: true }).fill("完成窄屏适配");
  await page.getByLabel("完成条件", { exact: true }).fill("不出现横向溢出");
  await page.screenshot({
    path: info.outputPath("窄屏目标编辑.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "创建并启用", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "暂停目标", exact: true }),
  ).toBeVisible();
  expect(
    JSON.parse(
      await fs.readFile(path.join(repo.root, ".agents/state.json"), "utf8"),
    ).activeGoal,
  ).toMatch(/^goal-/);
});

test("初始化提示、文件损坏与非法模式组合", async ({ page, repo }) => {
  await fs.unlink(path.join(repo.root, ".agents/docs/product.json"));
  await page.goto(`${repo.url}/#project`);
  await expect(page.getByText("先确认产品方向")).toBeVisible();
  await fs.writeFile(
    path.join(repo.root, ".agents/state.json"),
    JSON.stringify({ mode: "iteration", activeGoal: "bad" }),
  );
  await expect(page.getByText(/小步迭代不能同时启用目标/)).toBeVisible();
  await expect(
    page
      .getByRole("group", { name: "全局开发模式", exact: true })
      .getByRole("button", { name: "正常开发", exact: true }),
  ).toBeDisabled();
  await fs.writeFile(
    path.join(repo.root, ".agents/state.json"),
    JSON.stringify({ mode: "default", activeGoal: null }),
  );
  await expect(
    page
      .getByRole("group", { name: "全局开发模式", exact: true })
      .getByRole("button", { name: "正常开发", exact: true }),
  ).toBeEnabled();
  await fs.writeFile(path.join(repo.root, ".agents/goals/bad.json"), "{");
  await expect(page.getByText(/JSON 格式无效/)).toBeVisible();
});

test("快速开始布局、全局模式和项目页分离", async ({ page, repo }, info) => {
  await page.goto(repo.url);
  const mode = page.getByRole("region", { name: "开发模式面板" });
  const goal = page.getByRole("region", { name: "当前目标面板" });
  await expect(goal.getByText("尚未启用目标")).toBeVisible();
  const modeBox = await mode.boundingBox();
  const goalBox = await goal.boundingBox();
  expect(modeBox!.y).toBe(goalBox!.y);
  expect(goalBox!.x).toBeGreaterThan(modeBox!.x);
  await page
    .getByRole("group", { name: "全局开发模式", exact: true })
    .getByRole("button", { name: "小步迭代", exact: true })
    .click();
  await expect(
    page
      .getByRole("region", { name: "开发模式面板" })
      .getByRole("button", { name: "小步迭代", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.screenshot({
    path: info.outputPath("快速开始.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "项目", exact: true }).click();
  await expect(mode).toHaveCount(0);
  await expect(goal).toHaveCount(0);
  await expect(page.getByText("产品信息", { exact: true })).toBeVisible();
  await expect(page.locator("header").getByText("本地已连接")).toHaveCount(0);
  await expect(page.getByText("上下文，始终在本地")).toHaveCount(0);
  await expect(page.getByText("缩小验证范围，不跳过必要验证。")).toHaveCount(0);
  await page
    .getByRole("group", { name: "全局开发模式", exact: true })
    .getByRole("button", { name: "正常开发", exact: true })
    .click();
  await expect(
    page
      .getByRole("group", { name: "全局开发模式", exact: true })
      .getByRole("button", { name: "正常开发", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText("本地笔记", { exact: true })).toHaveCount(1);
  await expect(
    page
      .locator('[data-slot="sidebar-footer"]')
      .getByText("本地笔记", { exact: true }),
  ).toHaveCount(0);
  await page.screenshot({
    path: info.outputPath("项目产品信息.png"),
    fullPage: true,
  });
});

test("产品 Markdown 展示、原文编辑、新增字段与安全渲染", async ({
  page,
  repo,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const file = path.join(repo.root, ".agents/docs/product.json");
  const source =
    "## 验收清单\n\n- **离线可用**\n- 导出数据\n\n```js\nconst ready = true;\n```\n\n| 场景 | 结果 |\n| --- | --- |\n| 离线 | 通过 |\n\n[项目文档](https://example.com)\n\n<script>window.badMarkdown = true</script>\n\n[危险链接](javascript:alert(1))";
  const extended = { ...product, 特殊要求: source };
  await fs.writeFile(file, JSON.stringify(extended));
  await page.goto(`${repo.url}/#project`);
  await expect(
    page.getByRole("button", { name: "增加字段", exact: true }),
  ).toHaveCount(0);
  const requirements = page.getByRole("region", {
    name: "特殊要求",
    exact: true,
  });
  await expect(
    requirements.getByRole("heading", { name: "验收清单" }),
  ).toBeVisible();
  await expect(requirements.locator("strong")).toHaveText("离线可用");
  await expect(requirements.locator("pre code")).toContainText(
    "const ready = true;",
  );
  await expect(requirements.getByRole("table")).toBeVisible();
  await expect(
    requirements.getByRole("link", { name: "项目文档" }),
  ).toHaveAttribute("href", "https://example.com");
  expect(
    await requirements.locator("a").last().getAttribute("href"),
  ).not.toMatch(/^javascript:/);
  expect(await page.evaluate(() => Object.hasOwn(window, "badMarkdown"))).toBe(
    false,
  );
  await page.screenshot({ path: info.outputPath("Markdown展示.png") });
  await page.getByRole("button", { name: "编辑产品信息" }).click();
  const dialog = page.getByRole("dialog", {
    name: "编辑产品信息",
    exact: true,
  });
  await expect(
    dialog.getByRole("textbox", { name: "特殊要求", exact: true }),
  ).toHaveValue(source);
  await expect(
    dialog.getByRole("textbox", { name: "核心需求", exact: true }),
  ).toHaveValue(product.coreRequirements);
  await dialog.getByRole("button", { name: "增加字段", exact: true }).click();
  await expect(dialog.getByRole("combobox")).toHaveCount(0);
  await dialog.getByRole("button", { name: "添加到表单" }).click();
  await expect(dialog.getByText("请填写字段名称")).toBeVisible();
  await dialog.getByLabel("字段名称", { exact: true }).fill("summary");
  await dialog.getByRole("button", { name: "添加到表单" }).click();
  await expect(dialog.getByText("该字段已经存在")).toBeVisible();
  await dialog.getByLabel("字段名称", { exact: true }).fill("验收说明");
  await dialog.getByRole("button", { name: "添加到表单" }).click();
  const added =
    "### 发布检查\n\n- [x] 已完成\n- [ ] 待完成\n\n    保留代码缩进\n";
  await dialog
    .getByRole("textbox", { name: "验收说明", exact: true })
    .fill(added);
  await page.screenshot({ path: info.outputPath("Markdown原文编辑.png") });
  await dialog.getByRole("button", { name: "保存产品信息" }).click();
  await expect(dialog).toHaveCount(0);
  expect(JSON.parse(await fs.readFile(file, "utf8"))).toEqual({
    ...extended,
    验收说明: added,
  });
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "发布检查", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "编辑产品信息" }).click();
  await expect(
    dialog.getByRole("textbox", { name: "验收说明", exact: true }),
  ).toHaveValue(added);
  await dialog.getByRole("button", { name: "增加字段", exact: true }).click();
  await dialog.getByLabel("字段名称", { exact: true }).fill("未保存的字段");
  await dialog.getByRole("button", { name: "添加到表单" }).click();
  page.once("dialog", (prompt) => prompt.accept());
  await dialog.getByRole("button", { name: "取消", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  expect(JSON.parse(await fs.readFile(file, "utf8"))).not.toHaveProperty(
    "未保存的字段",
  );
  expect(errors).toEqual([]);
});

for (const width of [1180, 390]) {
  test(`独立滚动、切页宽度稳定和刷新保留位置 ${width}`, async ({
    page,
    repo,
  }, info) => {
    await page.setViewportSize({ width, height: 844 });
    const longProduct = {
      ...product,
      长文: Array.from(
        { length: 100 },
        (_, index) => `- 第 ${index + 1} 条说明`,
      ).join("\n"),
    };
    const file = path.join(repo.root, ".agents/docs/product.json");
    await fs.writeFile(file, JSON.stringify(longProduct));
    await page.goto(`${repo.url}/#project`);
    await expect(page.getByRole("heading", { name: "本地笔记" })).toBeVisible();
    const scroll = page.getByRole("region", {
      name: "页面内容",
      exact: true,
      includeHidden: true,
    });
    const headerBefore = await page.locator("header").boundingBox();
    const layout = await scroll.evaluate((el) => ({
      width: el.clientWidth,
      gutter: getComputedStyle(el).scrollbarGutter,
      overflow: el.scrollHeight > el.clientHeight,
    }));
    expect(layout.overflow).toBe(true);
    expect(layout.gutter).toBe("stable");
    await scroll.focus();
    await page.keyboard.press("End");
    await expect
      .poll(() =>
        scroll.evaluate(
          (el) => el.scrollTop + el.clientHeight >= el.scrollHeight - 1,
        ),
      )
      .toBe(true);
    await scroll.evaluate((el) => {
      el.scrollTop = 500;
    });
    expect(await page.locator("header").boundingBox()).toEqual(headerBefore);
    expect(
      await page.evaluate(
        () =>
          document.documentElement.scrollHeight <= innerHeight &&
          document.documentElement.scrollWidth <= innerWidth &&
          window.scrollY === 0,
      ),
    ).toBe(true);
    await fs.writeFile(
      file,
      JSON.stringify({ ...longProduct, 更新标记: "刷新完成" }),
    );
    await expect(page.getByText("刷新完成", { exact: true })).toHaveCount(1);
    expect(await scroll.evaluate((el) => el.scrollTop)).toBe(500);
    await page.evaluate(() => {
      location.hash = "start";
    });
    await expect(
      page.getByRole("region", { name: "当前目标面板" }),
    ).toBeVisible();
    await expect.poll(() => scroll.evaluate((el) => el.scrollTop)).toBe(0);
    expect(await scroll.evaluate((el) => el.clientWidth)).toBe(layout.width);
    expect(await page.locator("header").boundingBox()).toEqual(headerBefore);
    await page.evaluate(() => {
      location.hash = "project";
    });
    await expect(
      page.getByRole("button", { name: "编辑产品信息" }),
    ).toBeVisible();
    expect(await scroll.evaluate((el) => el.scrollTop)).toBe(0);
    await page.getByRole("button", { name: "编辑产品信息" }).click();
    const dialog = page.getByRole("dialog", { name: "编辑产品信息" });
    await expect(dialog).toBeVisible();
    expect(await scroll.evaluate((el) => el.clientWidth)).toBe(layout.width);
    await dialog.getByRole("button", { name: "取消", exact: true }).click();
    expect(await page.locator("header").boundingBox()).toEqual(headerBefore);
    await scroll.evaluate((el) => {
      el.scrollTop = 500;
    });
    await page.screenshot({ path: info.outputPath(`独立滚动-${width}.png`) });
  });
}

test("目标旧列表兼容、Markdown 原文编辑与状态操作", async ({
  page,
  repo,
}, info) => {
  const file = path.join(repo.root, ".agents/goals/markdown-goal.json");
  const legacy = {
    title: "**发布准备**",
    objective: "完成 **本地发布**",
    doneWhen: ["构建成功", "测试通过"],
    constraints: ["保留接口"],
    progress: ["完成检查"],
    附加说明: "## 发布注意\n\n请保留备份。",
  };
  await fs.writeFile(file, JSON.stringify(legacy));
  await page.goto(`${repo.url}/#goals/markdown-goal`);
  await expect(
    page.getByRole("heading", { name: "发布准备", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("构建成功", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "发布注意" })).toBeVisible();
  expect(JSON.parse(await fs.readFile(file, "utf8"))).toEqual(legacy);
  await page.getByRole("button", { name: "编辑目标", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "编辑目标", exact: true });
  await expect(
    dialog.getByRole("textbox", { name: "完成条件", exact: true }),
  ).toHaveValue("- 构建成功\n- 测试通过");
  await expect(
    dialog.getByRole("textbox", { name: "目标名称", exact: true }),
  ).toHaveValue("**发布准备**");
  await expect(
    dialog.getByRole("textbox", { name: "附加说明", exact: true }),
  ).toHaveValue(legacy.附加说明);
  const progress =
    "### 验证结果\n\n- [x] 单元测试通过\n- [ ] 等待验收\n\n    npm test\n";
  await dialog
    .getByRole("textbox", { name: "进展记录", exact: true })
    .fill(progress);
  await dialog.getByRole("button", { name: "保存目标", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "验证结果" })).toBeVisible();
  const saved = JSON.parse(await fs.readFile(file, "utf8"));
  expect(saved.progress).toBe(progress);
  expect(Object.values(saved).every((value) => typeof value === "string")).toBe(
    true,
  );
  await page.screenshot({ path: info.outputPath("目标Markdown.png") });
  await page.getByRole("button", { name: "启用目标", exact: true }).click();
  await page.getByRole("button", { name: "完成目标", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "重新启用", exact: true }),
  ).toBeVisible();
  expect(JSON.parse(await fs.readFile(file, "utf8"))).toEqual({
    ...saved,
    status: "completed",
  });
});
