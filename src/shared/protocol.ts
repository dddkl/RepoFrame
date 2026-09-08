import { z } from "zod";
import zhCN from "zod/v4/locales/zh-CN.js";

z.config(zhCN());

const text = z.string().trim().min(1, "不能为空");
const lines = z.array(text);
export const modeSchema = z.enum(["default", "iteration"]);
export const idSchema = z
  .string()
  .regex(
    /^[a-z0-9][a-z0-9_-]{0,79}$/,
    "标识只能包含小写字母、数字、连字符和下划线",
  )
  .refine(
    (id) => !/^(con|prn|aux|nul|com[0-9]|lpt[0-9])$/i.test(id),
    "不能使用系统保留名称",
  );
export const stateSchema = z
  .object({ mode: modeSchema, activeGoal: idSchema.nullable() })
  .passthrough()
  .refine(
    (state) => state.mode === "default" || state.activeGoal === null,
    "小步迭代不能同时启用目标，请先暂停或完成当前目标",
  );
export const productSchema = z
  .object({
    summary: text,
    users: text,
    coreRequirements: lines.min(1, "至少填写一条核心需求"),
    constraints: lines,
    nonGoals: lines,
  })
  .passthrough();
export const goalSchema = z
  .object({
    title: text,
    objective: text,
    doneWhen: lines.min(1, "至少填写一条完成条件"),
    constraints: lines,
    progress: lines,
    status: z.enum(["open", "completed"]).default("open"),
  })
  .passthrough();

export type Mode = z.infer<typeof modeSchema>;
export type State = z.infer<typeof stateSchema>;
export type Product = z.infer<typeof productSchema>;
export type Goal = z.infer<typeof goalSchema>;
export type FileValue<T> = { data: T; version: string };
export type GoalFile = FileValue<Goal> & { id: string };
export type Diagnostic = { file: string; message: string };
export type Snapshot = {
  repo: { name: string; path: string };
  state: FileValue<State> | null;
  product: FileValue<Product> | null;
  goals: GoalFile[];
  diagnostics: Diagnostic[];
};

export class AppError extends Error {
  constructor(
    message: string,
    public status = 400,
  ) {
    super(message);
  }
}

export function parse<T>(schema: z.ZodType<T>, value: unknown): T {
  const result = schema.safeParse(value);
  if (!result.success)
    throw new AppError(
      result.error.issues
        .map((i) => `${i.path.join(".") || "内容"}：${i.message}`)
        .join("；"),
      422,
    );
  return result.data;
}
