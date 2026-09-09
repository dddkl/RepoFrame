import { agentsUserContent } from "../src/agents-document";
import { replaceAgentsUserContent } from "../src/agents-document";

import { afterEach, beforeEach, expect, it } from "vitest";
import { promises as fs } from "node:fs";
import path from "node:path";
import { Store } from "../src/store";
import { Documents, DOC_INDEX } from "../src/documents";
import { initialize } from "../src/initialize";
import { createApp } from "../src/server";

let root: string;
let store: Store;
let docs: Documents;
beforeEach(async () => {
  const base = path.resolve(".tmp/documents");
  await fs.mkdir(base, { recursive: true });
  root = await fs.mkdtemp(path.join(base, "repo-"));
  store = new Store(root);
  docs = new Documents(store);
  await initialize(root, path.resolve("templates"));
});
afterEach(async () => {
  await fs.rm(root, { recursive: true, force: true });
});
const metadata = (file: string, category: string | null = null) => ({
  file,
  name: file,
  category,
  description: "修改代码时读取。",
});

it("共享类别、原始 Markdown、独立入口和产品排除", async () => {
  await store.write(".agents/docs/product.md", '{"summary":"保持不变"}', null);
  await docs.category(
    "工程要求",
    undefined,
    (await docs.snapshot()).index!.version,
  );
  let snapshot = await docs.snapshot();
  const category = snapshot.index!.data.categories[0].id;
  const source = "## 验证\n\n- **必要检查**\n\n    原始缩进\n";
  for (const file of ["testing.md", "nested/development.md"]) {
    await docs.save(
      file,
      source,
      null,
      metadata(file, category),
      snapshot.index!.version,
    );
    snapshot = await docs.snapshot();
  }
  expect(
    snapshot
      .index!.data.documents.filter((d) => d.category !== null)
      .map((d) => d.category),
  ).toEqual([category, category]);
  expect(snapshot.files).toHaveLength(2);
  expect(
    snapshot.files
      .filter((f) => f.file !== "repoframe-goal-progress.md")
      .every((f) => f.content === source),
  ).toBe(true);
  await docs.saveAgents("# 路由\n读取索引。\n", snapshot.agents.version);
  expect(agentsUserContent((await store.raw("AGENTS.md"))!)).toBe(
    "# 路由\n读取索引。\n",
  );
  expect(await store.raw(".agents/docs/product.md")).toBe(
    '{"summary":"保持不变"}',
  );
  expect((await docs.snapshot()).index!.data.documents).toHaveLength(2);
  await docs.category("工程规范", category, snapshot.index!.version);
  expect((await docs.snapshot()).index!.data.categories[0].name).toBe(
    "工程规范",
  );
});

it("外部 Markdown 自动发现，缺失文件和损坏索引不会被覆盖", async () => {
  await store.write(".agents/docs/external.md", "# 外部规则", null);
  let snapshot = await docs.snapshot();
  expect(snapshot.files[0].file).toBe("external.md");
  expect(snapshot.index!.data.documents).toEqual([]);
  await docs.save(
    "external.md",
    "# 已登记",
    snapshot.files[0].version,
    metadata("external.md"),
    snapshot.index!.version,
  );
  await fs.unlink(path.join(root, ".agents/docs/external.md"));
  expect(
    (await docs.snapshot()).diagnostics.some((d) =>
      d.message.includes("不存在"),
    ),
  ).toBe(true);
  await fs.writeFile(path.join(root, DOC_INDEX), "{");
  await expect(docs.category("新类别", undefined, null)).rejects.toMatchObject({
    status: 422,
  });
  expect(
    (await docs.snapshot()).diagnostics.some((d) => d.file === DOC_INDEX),
  ).toBe(true);
  expect(await store.raw(DOC_INDEX)).toBe("{");
});

it("拒绝空说明、非法类别、JSON 文件和越界路径", async () => {
  const snapshot = await docs.snapshot();
  for (const file of [
    "../outside.md",
    "a/../../escape.md",
    "F:/outside.md",
    "a\\bad.md",
    "product.json",
    "product.md",
    "index.json",
    "NUL.md",
  ]) {
    await expect(
      docs.save(file, "bad", null, metadata(file), snapshot.index!.version),
    ).rejects.toMatchObject({ status: 422 });
  }
  await expect(
    docs.save(
      "bad.md",
      "bad",
      null,
      { ...metadata("bad.md"), description: " " },
      snapshot.index!.version,
    ),
  ).rejects.toMatchObject({ status: 422 });
  await expect(
    docs.save(
      "bad.md",
      "bad",
      null,
      metadata("bad.md", "missing"),
      snapshot.index!.version,
    ),
  ).rejects.toMatchObject({ status: 422 });
  expect(await store.raw(".agents/docs/bad.md")).toBeNull();
});

it("正文和目录版本冲突不会覆盖其他修改", async () => {
  let snapshot = await docs.snapshot();
  await docs.save(
    "testing.md",
    "first",
    null,
    metadata("testing.md"),
    snapshot.index!.version,
  );
  snapshot = await docs.snapshot();
  await fs.writeFile(path.join(root, ".agents/docs/testing.md"), "external");
  await expect(
    docs.save(
      "testing.md",
      "overwrite",
      snapshot.files[0].version,
      metadata("testing.md"),
      snapshot.index!.version,
    ),
  ).rejects.toMatchObject({ status: 409 });
  await docs.category("新类别", undefined, snapshot.index!.version);
  await expect(
    docs.save(
      "new.md",
      "overwrite",
      null,
      metadata("new.md"),
      snapshot.index!.version,
    ),
  ).rejects.toMatchObject({ status: 409 });
  expect(await store.raw(".agents/docs/testing.md")).toBe("external");
  expect(await store.raw(".agents/docs/new.md")).toBeNull();
});

it("目录链接不能读取或写入", async () => {
  const outside = path.join(root, "outside");
  await fs.mkdir(outside);
  await fs.writeFile(path.join(outside, "secret.md"), "secret");
  await fs.symlink(
    outside,
    path.join(root, ".agents/docs/link"),
    process.platform === "win32" ? "junction" : "dir",
  );
  await expect(
    docs.save(
      "link/secret.md",
      "overwrite",
      null,
      metadata("link/secret.md"),
      (await docs.snapshot()).index!.version,
    ),
  ).rejects.toMatchObject({ status: 403 });
  expect(await fs.readFile(path.join(outside, "secret.md"), "utf8")).toBe(
    "secret",
  );
});

it("旧入口补充路由且重复初始化保留用户规则与状态", async () => {
  const route =
    "# 用户规则\n保持中文\n<!-- repoframe:start -->\n自定义已有规则\n<!-- repoframe:end -->\n尾部说明\n";
  await fs.writeFile(path.join(root, "AGENTS.md"), route);
  await fs.writeFile(
    path.join(root, ".agents/state.json"),
    '{"mode":"iteration","activeGoal":null}',
  );
  await initialize(root, path.resolve("templates"));
  const updated = await store.raw("AGENTS.md");
  expect(updated).toContain(".agents/docs/index.json");
  expect(updated).toContain("自定义已有规则");
  expect(updated).toContain("尾部说明");
  await initialize(root, path.resolve("templates"));
  expect(await store.raw("AGENTS.md")).toBe(updated);
  expect(await store.raw(".agents/state.json")).toBe(
    '{"mode":"iteration","activeGoal":null}',
  );
});

it("文档 API 使用同源写入和版本检查", async () => {
  const app = createApp(store, path.resolve("dist/web"), undefined, 7331);
  const request = (
    url: string,
    body?: unknown,
    origin = "http://127.0.0.1:7331",
  ) =>
    app.request(`http://127.0.0.1:7331/api/documents${url}`, {
      method: body ? "PUT" : "GET",
      headers: {
        host: "127.0.0.1:7331",
        origin,
        "content-type": "application/json",
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  const snapshot = await (await request("")).json();
  const body = {
    file: "api.md",
    content: "# API",
    metadata: metadata("api.md"),
    version: null,
    indexVersion: snapshot.index.version,
  };
  expect((await request("/file", body, "https://example.com")).status).toBe(
    403,
  );
  expect((await request("/file", body)).status).toBe(200);
  expect((await request("/file", body)).status).toBe(409);
});

it("用户约定保存不改变固定入口，拒绝区域标记和外部版本冲突", async () => {
  const before = (await store.raw("AGENTS.md"))!;
  const snapshot = await docs.snapshot();
  expect(snapshot.agents.content).toBe("");
  expect(JSON.stringify(snapshot)).not.toContain("## 1. 读取上下文");
  await docs.saveAgents("只修改相关代码。\n", snapshot.agents.version);
  expect(await store.raw("AGENTS.md")).toBe(
    replaceAgentsUserContent(before, "只修改相关代码。\n"),
  );
  await expect(
    docs.saveAgents("覆盖旧版本", snapshot.agents.version),
  ).rejects.toMatchObject({ status: 409 });
  await expect(
    docs.saveAgents(
      "<!-- repoframe:user:end -->",
      (await docs.snapshot()).agents.version,
    ),
  ).rejects.toMatchObject({ status: 422 });
});

it("直接路由的内部文档不展示、不能登记或编辑，init 清除旧索引项", async () => {
  const original = (await store.raw("AGENTS.md"))!;
  const internal = "internal-checks.md";
  await store.write(`.agents/docs/${internal}`, "固定规则", null);
  const index = (await docs.snapshot()).index!;
  await store.json(
    ".agents/docs/index.json",
    { ...index.data, documents: [...index.data.documents, metadata(internal)] },
    index.version,
  );
  await fs.writeFile(
    path.join(root, "AGENTS.md"),
    original.replace(
      "## 2. 工作模式",
      "始终读取 `.agents/docs/internal-checks.md`。\n\n## 2. 工作模式",
    ),
  );
  let snapshot = await docs.snapshot();
  expect(
    snapshot.files.some(
      (f) => f.file === internal || f.file === "repoframe-goal-progress.md",
    ),
  ).toBe(false);
  expect(snapshot.index!.data.documents.some((d) => d.file === internal)).toBe(
    false,
  );
  await expect(
    docs.save(
      internal,
      "覆盖",
      null,
      metadata(internal),
      snapshot.index!.version,
    ),
  ).rejects.toMatchObject({ status: 403 });
  await initialize(root, path.resolve("templates"));
  const rawIndex = JSON.parse((await store.raw(".agents/docs/index.json"))!);
  expect(
    rawIndex.documents.some((d: { file: string }) => d.file === internal),
  ).toBe(false);
  const initialized = await store.raw("AGENTS.md");
  await initialize(root, path.resolve("templates"));
  expect(await store.raw("AGENTS.md")).toBe(initialized);
  expect(await store.raw(`.agents/docs/${internal}`)).toBe("固定规则");
});
