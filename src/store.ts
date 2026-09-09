import { createHash, randomUUID } from "node:crypto";
import { promises as fs } from "node:fs";
import path from "node:path";
import { z } from "zod";
import {
  AppError,
  parse,
  stateSchema,
  productSchema,
  goalSchema,
  goalReadSchema,
  goalBasicReadSchema,
  idSchema,
  type Mode,
  type Snapshot,
  type FileValue,
  type Goal,
} from "./shared/protocol";
import { emptyProgress } from "./shared/progress";

export const STATE = ".agents/state.json";
export const PRODUCT = ".agents/docs/product.md";
export const GOALS = ".agents/goals";
const hash = (text: string) => createHash("sha256").update(text).digest("hex");
const missing = (error: unknown) =>
  (error as NodeJS.ErrnoException).code === "ENOENT";

export class Store {
  private queue: Promise<unknown> = Promise.resolve();
  constructor(public root: string) {
    this.root = path.resolve(root);
  }

  // Reject links at every existing segment, including junctions, before file access.
  async safePath(relative: string) {
    const base = await fs.realpath(this.root);
    const target = path.resolve(base, relative);
    if (!target.startsWith(base + path.sep))
      throw new AppError("文件路径超出当前仓库", 403);
    let current = base;
    for (const segment of path.relative(base, target).split(path.sep)) {
      current = path.join(current, segment);
      try {
        if ((await fs.lstat(current)).isSymbolicLink())
          throw new AppError("工作区文件不能通过符号链接访问", 403);
      } catch (error) {
        if (!missing(error)) throw error;
      }
    }
    return target;
  }

  async raw(relative: string): Promise<string | null> {
    try {
      return await fs.readFile(await this.safePath(relative), "utf8");
    } catch (error) {
      if (missing(error)) return null;
      throw error;
    }
  }

  async read<T>(
    relative: string,
    schema: z.ZodType<T>,
  ): Promise<FileValue<T> | null> {
    const source = await this.raw(relative);
    if (source === null) return null;
    let value: unknown;
    try {
      value = JSON.parse(source.replace(/^\uFEFF/, ""));
    } catch {
      throw new AppError("JSON 格式无效，请修正文件后重试", 422);
    }
    return { data: parse(schema, value), version: hash(source) };
  }

  async write(relative: string, content: string, expected: string | null) {
    const target = await this.safePath(relative);
    const old = await this.raw(relative);
    if ((old === null ? null : hash(old)) !== expected)
      throw new AppError("文件已被其他操作修改，请重新加载后再保存", 409);
    await fs.mkdir(path.dirname(target), { recursive: true });
    const temp = `${target}.${randomUUID()}.tmp`;
    try {
      await fs.writeFile(temp, content, { flag: "wx" });
      // Recheck after writing the temporary file to narrow the external-edit window.
      const latest = await this.raw(relative);
      if ((latest === null ? null : hash(latest)) !== expected)
        throw new AppError("文件已被其他操作修改，请重新加载后再保存", 409);
      await this.safePath(relative);
      await fs.rename(temp, target);
    } finally {
      await fs.rm(temp, { force: true });
    }
  }

  json(relative: string, value: unknown, expected: string | null) {
    return this.write(
      relative,
      JSON.stringify(value, null, 2) + "\n",
      expected,
    );
  }

  serial<T>(operation: () => Promise<T>): Promise<T> {
    const result = this.queue.then(operation);
    this.queue = result.catch(() => {});
    return result;
  }

  async snapshot(): Promise<Snapshot> {
    const result: Snapshot = {
      repo: { name: path.basename(this.root), path: this.root },
      state: null,
      product: null,
      goals: [],
      diagnostics: [],
    };
    const inspect = async <T>(file: string, schema: z.ZodType<T>) => {
      try {
        return await this.read(file, schema);
      } catch (error) {
        result.diagnostics.push({
          file,
          message:
            error instanceof AppError
              ? error.message
              : "无法读取文件，请检查访问权限",
        });
        return null;
      }
    };
    result.state = await inspect(STATE, stateSchema);
    try {
      result.product = await this.readProduct();
    } catch (error) {
      result.diagnostics.push({
        file: PRODUCT,
        message: (error as Error).message,
      });
    }
    if (!result.state && !result.diagnostics.some((d) => d.file === STATE))
      result.diagnostics.push({
        file: STATE,
        message: "尚未初始化，请先运行 npx repoframe init",
      });
    if (!result.product && !result.diagnostics.some((d) => d.file === PRODUCT))
      result.diagnostics.push({
        file: PRODUCT,
        message: "产品信息尚未确认，请通过初始化 Skill 提炼 PRD",
      });
    try {
      const entries = await fs.readdir(await this.safePath(GOALS), {
        withFileTypes: true,
      });
      for (const entry of entries.sort((a, b) =>
        a.name.localeCompare(b.name),
      )) {
        if (!entry.name.endsWith(".json")) continue;
        const id = entry.name.slice(0, -5);
        if (!idSchema.safeParse(id).success) {
          result.diagnostics.push({
            file: `${GOALS}/${entry.name}`,
            message: "目标文件名不是有效标识",
          });
          continue;
        }
        const file = `${GOALS}/${entry.name}`;
        try {
          const goal = await this.read(file, goalReadSchema);
          if (goal) result.goals.push({ id, ...goal });
        } catch (error) {
          const message = (error as Error).message;
          const basic = await inspect(file, goalBasicReadSchema);
          if (basic)
            result.goals.push({
              id,
              version: basic.version,
              data: { ...basic.data, progress: emptyProgress() },
              progressError: `进展路径无效：${message}。旧进展请运行 init 迁移。`,
            });
        }
      }
    } catch (error) {
      if (!missing(error))
        result.diagnostics.push({
          file: GOALS,
          message:
            error instanceof AppError ? error.message : "无法读取目标目录",
        });
    }
    const active = result.state?.data.activeGoal;
    if (active) {
      const goal = result.goals.find((g) => g.id === active);
      if (!goal || goal.data.status === "completed")
        result.diagnostics.push({
          file: STATE,
          message: "当前目标不存在、无效或已经完成，请暂停当前引用后重新选择",
        });
    }
    return result;
  }

  private async state(version: unknown) {
    const state = await this.read(STATE, stateSchema);
    if (!state) throw new AppError("请先初始化仓库", 409);
    if (typeof version !== "string" || version !== state.version)
      throw new AppError("项目状态已变化，请重新加载后重试", 409);
    return state;
  }

  setMode(mode: Mode, version: unknown) {
    return this.serial(async () => {
      const state = await this.state(version);
      if (mode === "iteration" && state.data.activeGoal)
        throw new AppError("请先暂停或完成当前目标，再切换到小步迭代", 409);
      await this.json(
        STATE,
        parse(stateSchema, { ...state.data, mode }),
        state.version,
      );
    });
  }

  saveProduct(value: unknown, version: unknown) {
    return this.serial(async () => {
      const current = await this.readProduct();
      if (version !== (current?.version ?? ""))
        throw new AppError("产品信息已变化，请重新加载后保存", 409);
      const content = parse(productSchema, value);
      await this.write(
        PRODUCT,
        content,
        current?.version.startsWith("md:") ? current.version.slice(3) : null,
      );
    });
  }

  async readProduct(): Promise<FileValue<string> | null> {
    const markdown = await this.raw(PRODUCT);
    if (markdown !== null)
      return { data: markdown, version: `md:${hash(markdown)}` };
    return null;
  }

  createGoal(
    value: unknown,
    id: string | undefined,
    activate: boolean,
    stateVersion: unknown,
  ) {
    return this.serial(async () => {
      const data = parse(goalSchema, value);
      const goalId = parse(idSchema, id || `goal-${randomUUID().slice(0, 8)}`);
      const state = await this.state(stateVersion);
      await this.json(
        `${GOALS}/${goalId}.json`,
        { ...data, status: "open" },
        null,
      );
      if (activate)
        await this.json(
          STATE,
          { ...state.data, mode: "default", activeGoal: goalId },
          state.version,
        );
      return goalId;
    });
  }

  editGoal(id: string, value: unknown, version: unknown) {
    return this.serial(async () => {
      const file = `${GOALS}/${parse(idSchema, id)}.json`;
      const current = await this.read(file, goalReadSchema);
      if (!current) throw new AppError("目标不存在", 404);
      if (version !== current.version)
        throw new AppError("目标已变化，请重新加载后保存", 409);
      const data = parse(goalSchema, value);
      await this.json(
        file,
        { ...current.data, ...data, status: current.data.status },
        current.version,
      );
    });
  }

  goalAction(
    id: string,
    action: "activate" | "pause" | "complete",
    version: unknown,
    stateVersion: unknown,
  ) {
    return this.serial(async () => {
      const safeId = parse(idSchema, id);
      const state = await this.state(stateVersion);
      // Allow a stale/missing active reference to be explicitly paused.
      if (action === "pause") {
        if (state.data.activeGoal !== safeId)
          throw new AppError("该目标当前未启用", 409);
        await this.json(
          STATE,
          { ...state.data, activeGoal: null },
          state.version,
        );
        return;
      }
      const file = `${GOALS}/${safeId}.json`;
      const goal = await this.read(file, goalReadSchema);
      if (!goal) throw new AppError("目标不存在", 404);
      if (version !== goal.version)
        throw new AppError("目标已变化，请重新加载后重试", 409);
      if (action === "activate") {
        if (goal.data.status === "completed")
          await this.json(file, { ...goal.data, status: "open" }, goal.version);
        await this.json(
          STATE,
          { ...state.data, mode: "default", activeGoal: safeId },
          state.version,
        );
      } else {
        // Clear the reference first: interruption must not leave a completed active goal.
        if (state.data.activeGoal === safeId)
          await this.json(
            STATE,
            { ...state.data, activeGoal: null },
            state.version,
          );
        await this.json(
          file,
          { ...goal.data, status: "completed" } satisfies Goal,
          goal.version,
        );
      }
    });
  }
}
