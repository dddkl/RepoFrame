import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { promises as fs } from "node:fs";
import path from "node:path";
import { Store, STATE, PRODUCT } from "../src/store";
import { initialize } from "../src/initialize";
import { stateSchema } from "../src/shared/protocol";

let root: string;
let store: Store;
const goal = {
  title: "邮箱认证",
  objective: "完成邮箱登录流程",
  doneWhen: ["可以登录", "受保护路由正常工作"],
  constraints: [],
  progress: [],
  status: "open" as const,
};
const product = {
  summary: "测试产品",
  users: "开发者",
  coreRequirements: ["管理开发上下文"],
  constraints: [],
  nonGoals: [],
};
const state = async () => (await store.read(STATE, stateSchema))!;
const current = async (id: string) =>
  (await store.snapshot()).goals.find((g) => g.id === id)!;

beforeEach(async () => {
  const base = path.resolve(".tmp/unit");
  await fs.mkdir(base, { recursive: true });
  root = await fs.mkdtemp(path.join(base, "repo-"));
  store = new Store(root);
  await initialize(root, path.resolve("templates"));
});
afterEach(async () => {
  await fs.rm(root, { recursive: true, force: true });
});

describe("常驻模式与按需目标", () => {
  it("初始化无目标且不虚构产品信息", async () => {
    expect((await state()).data).toEqual({ mode: "default", activeGoal: null });
    expect((await store.snapshot()).goals).toEqual([]);
    expect(await store.raw(PRODUCT)).toBeNull();
  });
  it("切换模式持久化，普通创建不退出迭代模式", async () => {
    await store.setMode("iteration", (await state()).version);
    await store.createGoal(goal, "auth", false, (await state()).version);
    expect((await state()).data).toEqual({
      mode: "iteration",
      activeGoal: null,
    });
    expect((await current("auth")).data.status).toBe("open");
  });
  it("启用恢复正常模式，阻止迭代，暂停保留进展后允许迭代", async () => {
    await store.setMode("iteration", (await state()).version);
    await store.createGoal(
      { ...goal, progress: ["已检查现有路由"] },
      "auth",
      true,
      (await state()).version,
    );
    expect((await state()).data).toEqual({
      mode: "default",
      activeGoal: "auth",
    });
    await expect(
      store.setMode("iteration", (await state()).version),
    ).rejects.toMatchObject({ status: 409 });
    await store.goalAction(
      "auth",
      "pause",
      (await current("auth")).version,
      (await state()).version,
    );
    expect((await state()).data).toEqual({ mode: "default", activeGoal: null });
    expect((await current("auth")).data.progress).toEqual(["已检查现有路由"]);
    await store.setMode("iteration", (await state()).version);
    await store.goalAction(
      "auth",
      "activate",
      (await current("auth")).version,
      (await state()).version,
    );
    expect((await state()).data.mode).toBe("default");
  });
  it("完成清除当前引用，重新启用恢复 open", async () => {
    await store.createGoal(goal, "auth", true, (await state()).version);
    await store.goalAction(
      "auth",
      "complete",
      (await current("auth")).version,
      (await state()).version,
    );
    expect((await current("auth")).data.status).toBe("completed");
    expect((await state()).data).toEqual({ mode: "default", activeGoal: null });
    await store.goalAction(
      "auth",
      "activate",
      (await current("auth")).version,
      (await state()).version,
    );
    expect((await current("auth")).data.status).toBe("open");
  });
  it("替换当前目标保留前一个目标，完成非当前目标不影响当前引用", async () => {
    await store.createGoal(goal, "one", true, (await state()).version);
    await store.createGoal(goal, "two", true, (await state()).version);
    await store.goalAction(
      "one",
      "complete",
      (await current("one")).version,
      (await state()).version,
    );
    expect((await state()).data.activeGoal).toBe("two");
  });
  it("旧目标兼容，外部进展刷新，并保留扩展字段", async () => {
    const { status: _, ...legacy } = goal;
    await fs.writeFile(
      path.join(root, ".agents/goals/legacy.json"),
      JSON.stringify({ ...legacy, extra: "保留", progress: ["外部修改"] }),
    );
    expect((await current("legacy")).data.status).toBe("open");
    const old = await current("legacy");
    await store.editGoal("legacy", { ...goal, title: "新标题" }, old.version);
    expect((await current("legacy")).data.extra).toBe("保留");
  });
});

describe("文件保全与错误诊断", () => {
  it("重复初始化保留原始入口、PRD、产品和状态且无重复路由", async () => {
    await fs.writeFile(
      path.join(root, "AGENTS.md"),
      "# 团队约定\n保留此内容\n",
    );
    await fs.writeFile(path.join(root, "PRD.md"), "原始产品需求");
    await fs.writeFile(path.join(root, PRODUCT), JSON.stringify(product));
    await store.setMode("iteration", (await state()).version);
    await initialize(root, path.resolve("templates"));
    const first = await store.raw("AGENTS.md");
    await initialize(root, path.resolve("templates"));
    expect(await store.raw("AGENTS.md")).toBe(first);
    expect(first).toContain("保留此内容");
    expect(first?.match(/repoframe:start/g)).toHaveLength(1);
    expect(await store.raw("PRD.md")).toBe("原始产品需求");
    expect((await state()).data.mode).toBe("iteration");
    expect((await store.snapshot()).product?.data.summary).toBe("测试产品");
  });
  it("拒绝重复 ID、保留名称和越界 ID", async () => {
    await store.createGoal(goal, "auth", false, (await state()).version);
    await expect(
      store.createGoal(goal, "auth", false, (await state()).version),
    ).rejects.toMatchObject({ status: 409 });
    for (const id of ["../escape", "CON", "con", "x/y", "x\\y"])
      await expect(
        store.createGoal(goal, id, false, (await state()).version),
      ).rejects.toMatchObject({ status: 422 });
    await expect(store.raw("../outside")).rejects.toMatchObject({
      status: 403,
    });
  });
  it("拒绝符号链接目录，避免通过 junction 访问其他目录", async () => {
    const external = path.join(root, "external");
    await fs.mkdir(external);
    await fs.symlink(
      external,
      path.join(root, ".agents/link"),
      process.platform === "win32" ? "junction" : "dir",
    );
    await expect(store.raw(".agents/link/secret.json")).rejects.toMatchObject({
      status: 403,
    });
  });
  it("损坏目标不阻断其他文件；非法状态不静默修复", async () => {
    await store.createGoal(goal, "good", false, (await state()).version);
    await fs.writeFile(path.join(root, ".agents/goals/bad.json"), "{");
    const invalid = JSON.stringify({ mode: "iteration", activeGoal: "good" });
    await fs.writeFile(path.join(root, STATE), invalid);
    const snapshot = await store.snapshot();
    expect(snapshot.goals).toHaveLength(1);
    expect(snapshot.state).toBeNull();
    expect(snapshot.diagnostics).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ file: STATE }),
        expect.objectContaining({ file: ".agents/goals/bad.json" }),
      ]),
    );
    expect(await store.raw(STATE)).toBe(invalid);
  });
  it("失效的当前目标可以显式暂停", async () => {
    await fs.writeFile(
      path.join(root, STATE),
      JSON.stringify({ mode: "default", activeGoal: "missing" }),
    );
    expect(
      (await store.snapshot()).diagnostics.some((d) =>
        d.message.includes("当前目标"),
      ),
    ).toBe(true);
    await store.goalAction(
      "missing",
      "pause",
      undefined,
      (await state()).version,
    );
    expect((await state()).data.activeGoal).toBeNull();
  });
  it("并发版本冲突不覆盖外部编辑，产品扩展字段保留", async () => {
    await fs.writeFile(
      path.join(root, PRODUCT),
      JSON.stringify({ ...product, extra: "原始字段" }),
    );
    const old = (await store.snapshot()).product!;
    await store.saveProduct({ ...product, summary: "更新" }, old.version);
    await expect(store.saveProduct(product, old.version)).rejects.toMatchObject(
      { status: 409 },
    );
    expect((await store.snapshot()).product?.data.extra).toBe("原始字段");
    const before = await state();
    const results = await Promise.allSettled([
      store.setMode("iteration", before.version),
      store.setMode("iteration", before.version),
    ]);
    expect(results.filter((r) => r.status === "rejected")).toHaveLength(1);
  });
});
