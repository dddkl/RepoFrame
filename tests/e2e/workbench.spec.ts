import { graph } from "../fixtures/progress";

import { test as base, expect } from "@playwright/test";
import { promises as fs } from "node:fs";
import path from "node:path";
import { spawn, execFileSync, type ChildProcess } from "node:child_process";
import { createServer } from "node:net";

const product =
  "# 产品说明\n\n一个离线优先的个人笔记工具，让想法、资料与写作有序沉淀。\n\n## 主要用户\n\n独立开发者与写作者\n\n## 核心需求\n\n- 创建、编辑和检索 Markdown 笔记\n- 按标签整理内容\n- 所有内容保存在本地\n";

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
    await fs.writeFile(path.join(root, ".agents/docs/product.md"), product);
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
  goal.progress = graph;
  await fs.writeFile(file, JSON.stringify(goal));
  await expect(page.getByText("界面实现", { exact: true })).toBeVisible();
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
  await expect(page.getByText("界面实现", { exact: true })).toBeVisible();
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
    .getByRole("textbox", { name: "产品 Markdown 正文", exact: true })
    .fill("尚未保存的本地草稿");
  const file = path.join(repo.root, ".agents/docs/product.md");
  await fs.writeFile(file, "来自 Agent 的新描述");
  await expect(page.getByText("文件在编辑期间发生变化")).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "产品 Markdown 正文", exact: true }),
  ).toHaveValue("尚未保存的本地草稿");
  await expect(
    page.getByRole("button", { name: "保存产品信息" }),
  ).toBeDisabled();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "重新加载", exact: true }).click();
  await expect(
    page.getByRole("textbox", { name: "产品 Markdown 正文", exact: true }),
  ).toHaveValue(/来自 Agent 的新描述/);
  await page
    .getByRole("textbox", { name: "产品 Markdown 正文", exact: true })
    .fill("已确认的本地笔记工具");
  await page.screenshot({
    path: info.outputPath("产品编辑.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "保存产品信息" }).click();
  await expect(
    page.getByRole("dialog", { name: "编辑产品信息", exact: true }),
  ).toHaveCount(0);
  expect(
    await fs.readFile(path.join(repo.root, ".agents/docs/product.md"), "utf8"),
  ).toBe("已确认的本地笔记工具");
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
  await fs.unlink(path.join(repo.root, ".agents/docs/product.md"));
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
  expect(goalBox!.y).toBeGreaterThan(modeBox!.y + modeBox!.height);
  expect(goalBox!.x).toBe(modeBox!.x);
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

test("产品完整 Markdown 编辑、无预设字段与安全渲染", async ({
  page,
  repo,
}, info) => {
  const file = path.join(repo.root, ".agents/docs/product.md");
  const source =
    "# 自由产品文档\n\n- **离线可用**\n\n| 场景 | 结果 |\n| --- | --- |\n| 离线 | 通过 |\n\n<script>window.badMarkdown = true</script>";
  await fs.writeFile(file, source);
  await page.goto(repo.url + "/#project");
  await expect(
    page.getByRole("heading", { name: "自由产品文档" }),
  ).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
  expect(await page.evaluate(() => Object.hasOwn(window, "badMarkdown"))).toBe(
    false,
  );
  await expect(
    page.getByRole("button", { name: "刷新", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "编辑产品信息" }).click();
  const dialog = page.getByRole("dialog", {
    name: "编辑产品信息",
    exact: true,
  });
  await expect(dialog.getByRole("textbox")).toHaveCount(1);
  await expect(dialog.getByRole("button", { name: "增加字段" })).toHaveCount(0);
  await expect(dialog.getByRole("textbox")).toHaveValue(source);
  const changed = source + "\n\n## 发布检查\n\n- [x] 完成\n\n    保留缩进\n";
  await dialog.getByRole("textbox").fill(changed);
  await dialog.getByRole("button", { name: "保存产品信息" }).click();
  await expect(dialog).toHaveCount(0);
  expect(await fs.readFile(file, "utf8")).toBe(changed);
  await expect(page.getByRole("heading", { name: "发布检查" })).toBeVisible();
  await page.screenshot({ path: info.outputPath("产品完整Markdown.png") });
  await page.getByRole("button", { name: "文档", exact: true }).click();
  await expect(
    page
      .getByRole("navigation", { name: "文档目录" })
      .getByRole("button", { name: "product.md" }),
  ).toHaveCount(0);
});

for (const width of [1180, 390]) {
  test(`独立滚动、切页宽度稳定和刷新保留位置 ${width}`, async ({
    page,
    repo,
  }, info) => {
    await page.setViewportSize({ width, height: 844 });
    const longProduct =
      product +
      "\n\n" +
      Array.from(
        { length: 80 },
        (_, i) => `## 要求 ${i}\n\n用于检查滚动区域的详细产品说明。`,
      ).join("\n\n");
    const file = path.join(repo.root, ".agents/docs/product.md");
    await fs.writeFile(file, longProduct);
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
    await fs.writeFile(file, longProduct + "\n\n刷新完成");
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
    progress: graph,
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
  await expect(
    dialog.getByRole("textbox", { name: "进展记录", exact: true }),
  ).toHaveCount(0);
  await dialog.getByRole("button", { name: "保存目标", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  const saved = JSON.parse(await fs.readFile(file, "utf8"));
  expect(saved.progress).toEqual(graph);
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

test("文档分类、Markdown 编辑、外部同步和冲突保护", async ({
  page,
  repo,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(`${repo.url}/#docs`);
  await expect(
    page.getByRole("button", { name: "新增文件", exact: true }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "新增类别", exact: true }).click();
  await page.getByLabel("类别名称", { exact: true }).fill("工程要求");
  await page.getByRole("button", { name: "保存类别", exact: true }).click();
  await expect(
    page.getByRole("dialog", { name: "新增类别", exact: true }),
  ).toHaveCount(0);
  for (const [name, file] of [
    ["验证要求", "testing.md"],
    ["开发约定", "development.md"],
  ]) {
    await page.getByRole("button", { name: "新增文件", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "新增文件", exact: true });
    await dialog.getByLabel("名称", { exact: true }).fill(name);
    await dialog.getByLabel("文件路径", { exact: true }).fill(file);
    await dialog.getByRole("button", { name: "保存", exact: true }).click();
    await expect(
      dialog.getByText("请填写何时读取", { exact: true }),
    ).toBeVisible();
    await dialog
      .getByLabel("何时读取", { exact: true })
      .fill("修改代码或执行验证时读取。");
    await dialog
      .getByLabel("类别", { exact: true })
      .selectOption({ label: "工程要求" });
    await dialog
      .getByLabel("Markdown 正文", { exact: true })
      .fill(
        "## 必要验证\n\n- **针对性检查**\n- [ ] 完成测试\n\n    保留缩进\n",
      );
    await dialog.getByRole("button", { name: "保存", exact: true }).click();
    await expect(dialog).toHaveCount(0);
    await expect(
      page.getByRole("heading", { name: "必要验证", exact: true }),
    ).toBeVisible();
  }
  const indexPath = path.join(repo.root, ".agents/docs/index.json");
  const index = JSON.parse(await fs.readFile(indexPath, "utf8"));
  expect(index.documents).toHaveLength(2);
  expect(
    new Set(
      index.documents
        .filter((d: { category: string | null }) => d.category !== null)
        .map((d: { category: string }) => d.category),
    ).size,
  ).toBe(1);
  expect(
    index.documents.every((d: { file: string }) => d.file.endsWith(".md")),
  ).toBe(true);
  await page.screenshot({ path: info.outputPath("文档视图.png") });
  const external = path.join(repo.root, ".agents/docs/external.md");
  await fs.writeFile(external, "# 外部新增\n");
  await expect(
    page.getByRole("heading", { name: "待补充说明", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "external.md", exact: true }).click();
  await page.getByRole("button", { name: "编辑文档", exact: true }).click();
  const dialog = page.getByRole("dialog", {
    name: /^(编辑文档|编辑用户约定)$/,
  });
  await dialog.getByLabel("名称", { exact: true }).fill("外部规则");
  await dialog
    .getByLabel("何时读取", { exact: true })
    .fill("每次开始开发时读取。");
  await dialog.getByRole("button", { name: "保存", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await page.getByRole("button", { name: "编辑文档", exact: true }).click();
  await expect(dialog.getByLabel("Markdown 正文", { exact: true })).toHaveValue(
    "# 外部新增\n",
  );
  await dialog.getByLabel("Markdown 正文", { exact: true }).fill("本地草稿");
  await fs.writeFile(external, "# 外部更新\n");
  await expect(
    dialog.getByText("文件或目录在编辑期间发生变化", { exact: true }),
  ).toBeVisible();
  await expect(dialog.getByLabel("Markdown 正文", { exact: true })).toHaveValue(
    "本地草稿",
  );
  await expect(
    dialog.getByRole("button", { name: "保存", exact: true }),
  ).toBeDisabled();
  page.once("dialog", (d) => d.accept());
  await dialog.getByRole("button", { name: "重新加载", exact: true }).click();
  await expect(dialog.getByLabel("Markdown 正文", { exact: true })).toHaveValue(
    "# 外部更新\n",
  );
  await dialog.getByRole("button", { name: "取消", exact: true }).click();
  await page.getByRole("button", { name: "AGENTS.md", exact: true }).click();
  await page.getByRole("button", { name: "编辑文档", exact: true }).click();
  const route = await dialog
    .getByLabel("Markdown 正文", { exact: true })
    .inputValue();
  await dialog
    .getByLabel("Markdown 正文", { exact: true })
    .fill(`${route}\n## 用户规则\n保持中文\n`);
  await dialog.getByRole("button", { name: "保存", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "用户规则", exact: true }),
  ).toBeVisible();
  expect(
    await fs.readFile(path.join(repo.root, "AGENTS.md"), "utf8"),
  ).toContain("保持中文");
  expect(
    await fs.readFile(path.join(repo.root, ".agents/docs/product.md"), "utf8"),
  ).toEqual(product);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "编辑文档", exact: true }).click();
  await expect(
    dialog.getByRole("button", { name: "保存", exact: true }),
  ).toBeInViewport();
  await page.screenshot({ path: info.outputPath("文档编辑移动端.png") });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});

test("进展邻域、完整分支图、消息展开及完成保留路径", async ({
  page,
  repo,
}, info) => {
  const file = path.join(repo.root, ".agents/goals/path.json");
  const data = {
    title: "执行路径样例",
    objective: "检查关键阶段",
    doneWhen: "主要流程通过验证",
    constraints: "保持简单",
    status: "open",
    progress: graph,
  };
  await fs.writeFile(file, JSON.stringify(data));
  await page.goto(`${repo.url}/#goals/path`);
  const summary = page.getByRole("region", { name: "进展摘要", exact: true });
  await expect(summary.getByText("界面实现", { exact: true })).toBeVisible();
  await expect(summary.getByText("旧方案", { exact: true })).toHaveCount(0);
  const conditions = page
    .locator('[data-slot="card"]')
    .filter({ has: page.getByText("完成条件", { exact: true }) });
  const constraints = page
    .locator('[data-slot="card"]')
    .filter({ has: page.getByText("任务约束", { exact: true }) });
  const left = await conditions.boundingBox(),
    below = await constraints.boundingBox(),
    right = await summary.boundingBox();
  expect(left!.x).toBe(below!.x);
  expect(below!.y).toBeGreaterThan(left!.y);
  expect(right!.x).toBeGreaterThan(left!.x);
  await page.screenshot({ path: info.outputPath("进展摘要.png") });
  await page.getByRole("button", { name: "查看完整路径" }).click();
  await expect(page).toHaveURL(/goals\/path\/progress$/);
  const full = page.getByRole("region", { name: "完整执行路径", exact: true });
  await expect(full.getByText("旧方案", { exact: true })).toBeVisible();
  await expect(full.locator('[data-edge="2-4"]')).toHaveCount(1);
  await expect(full.locator('[data-edge="3-4"]')).toHaveCount(1);
  const before = await full.locator('[data-edge="3-4"]').getAttribute("d");
  await full.getByRole("button", { name: "后端实现", exact: true }).click();
  await expect(
    full.getByText("接口实现通过验证。", { exact: true }),
  ).toBeVisible();
  await expect
    .poll(() => full.locator('[data-edge="3-4"]').getAttribute("d"))
    .not.toBe(before);
  await page.screenshot({ path: info.outputPath("完整执行路径.png") });
  await page.reload();
  await expect(full.getByText("联合验证", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: info.outputPath("路径窄屏.png") });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "返回目标详情" }).click();
  await page.getByRole("button", { name: "完成目标", exact: true }).click();
  await expect(
    page.getByText("目标已完成，路径仍有未完成节点", { exact: true }),
  ).toBeVisible();
  expect(JSON.parse(await fs.readFile(file, "utf8")).progress).toEqual(graph);
  const broken = { ...data, progress: { ...graph, current: 999 } };
  await fs.writeFile(file, JSON.stringify(broken));
  await expect(summary.getByText(/进展路径无效/)).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "执行路径样例", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "编辑目标", exact: true }),
  ).toBeDisabled();
});
