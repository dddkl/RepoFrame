import { z } from "zod";
import { idSchema, type Diagnostic, type FileValue } from "./protocol";

export const documentPathSchema = z.string().refine((file) => {
  if (
    !file.endsWith(".md") ||
    file.length > 240 ||
    file.toLowerCase() === "product.md"
  )
    return false;
  return file
    .split("/")
    .every(
      (part) =>
        !!part &&
        part !== "." &&
        part !== ".." &&
        !/[\\<>:"|?*\x00-\x1f]/.test(part) &&
        !/[. ]$/.test(part) &&
        !/^(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\.|$)/i.test(part),
    );
}, "使用 docs 内的相对 Markdown 路径，例如 testing.md");
export const categorySchema = z.object({
  id: idSchema,
  name: z.string().trim().min(1).max(100),
});
export const documentSchema = z.object({
  name: z.string().trim().min(1).max(150),
  category: idSchema.nullable(),
  file: documentPathSchema,
  description: z.string().trim().min(1, "请填写何时读取").max(500),
});
export const documentIndexSchema = z
  .object({
    categories: z.array(categorySchema),
    documents: z.array(documentSchema),
  })
  .superRefine((value, ctx) => {
    const ids = value.categories.map((c) => c.id);
    const names = value.categories.map((c) => c.name.toLowerCase());
    const files = value.documents.map((d) => d.file.toLowerCase());
    if (
      new Set(ids).size !== ids.length ||
      new Set(names).size !== names.length
    )
      ctx.addIssue({ code: "custom", message: "类别不能重复" });
    if (new Set(files).size !== files.length)
      ctx.addIssue({ code: "custom", message: "文件不能重复登记" });
    if (
      value.documents.some(
        (d) => d.category !== null && !ids.includes(d.category),
      )
    )
      ctx.addIssue({ code: "custom", message: "所属类别不存在" });
  });
export type DocumentIndex = z.infer<typeof documentIndexSchema>;
export type DocumentEntry = z.infer<typeof documentSchema>;
export type DocumentFile = {
  file: string;
  content: string | null;
  version: string | null;
};
export type DocumentsSnapshot = {
  index: FileValue<DocumentIndex> | null;
  agents: DocumentFile;
  files: DocumentFile[];
  diagnostics: Diagnostic[];
};
export const emptyIndex = (): DocumentIndex => ({
  categories: [],
  documents: [],
});
