import { z } from "zod";
import zhCN from "zod/v4/locales/zh-CN.js";

z.config(zhCN());

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
const markdown = z.string();
const requiredMarkdown = markdown.refine(
  (value) => value.trim().length > 0,
  "不能为空",
);
export const productSchema = z
  .object({
    summary: requiredMarkdown,
    users: requiredMarkdown,
    coreRequirements: requiredMarkdown,
    constraints: markdown,
    nonGoals: markdown,
  })
  .catchall(markdown);

// Read old files without changing them. An explicit save writes the string format.
export function legacyMarkdown(value: unknown): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value) && value.every((item) => typeof item === "string"))
    return value.map((item) => `- ${item.replace(/\n/g, "\n  ")}`).join("\n");
  // Fence other legacy JSON values so no information is lost in conversion.
  const source = JSON.stringify(value, null, 2) ?? "null";
  const fence = "`".repeat(
    Math.max(
      3,
      ...Array.from(source.matchAll(/`+/g), (match) => match[0].length + 1),
    ),
  );
  return `${fence}json\n${source}\n${fence}`;
}
function normalizeMarkdownFields(value: unknown) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return value;
  return Object.fromEntries(
    Object.entries(value).map(([key, item]) => [key, legacyMarkdown(item)]),
  );
}
export const productReadSchema = z.preprocess(
  normalizeMarkdownFields,
  productSchema,
);
export const goalSchema = z
  .object({
    title: requiredMarkdown,
    objective: requiredMarkdown,
    doneWhen: requiredMarkdown,
    constraints: markdown,
    progress: markdown,
    status: z.enum(["open", "completed"]).default("open"),
  })
  .catchall(markdown);
export const goalReadSchema = z.preprocess(normalizeMarkdownFields, goalSchema);

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
