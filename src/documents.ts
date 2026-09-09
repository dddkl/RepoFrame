import { promises as fs } from "node:fs";
import { createHash, randomUUID } from "node:crypto";
import { Store } from "./store";
import { AppError, parse } from "./shared/protocol";
import {
  agentsUserContent,
  replaceAgentsUserContent,
  directDocuments,
} from "./agents-document";
import {
  categorySchema,
  documentIndexSchema,
  documentPathSchema,
  documentSchema,
  emptyIndex,
  type DocumentFile,
  type DocumentsSnapshot,
} from "./shared/documents";

export const DOC_INDEX = ".agents/docs/index.json";
const digest = (text: string) =>
  createHash("sha256").update(text).digest("hex");
export class Documents {
  constructor(private store: Store) {}
  private async text(file: string, root = false): Promise<DocumentFile> {
    const content = await this.store.raw(
      root ? "AGENTS.md" : `.agents/docs/${parse(documentPathSchema, file)}`,
    );
    return {
      file,
      content: root && content !== null ? agentsUserContent(content) : content,
      version: content === null ? null : digest(content),
    };
  }
  async snapshot(): Promise<DocumentsSnapshot> {
    const result: DocumentsSnapshot = {
      index: null,
      agents: { file: "AGENTS.md", content: null, version: null },
      files: [],
      diagnostics: [],
    };
    const inspect = async (file: string, fn: () => Promise<void>) => {
      try {
        await fn();
      } catch (error) {
        result.diagnostics.push({
          file,
          message: error instanceof Error ? error.message : "无法读取文件",
        });
      }
    };
    await inspect(DOC_INDEX, async () => {
      result.index = await this.store.read(DOC_INDEX, documentIndexSchema);
    });
    let agentsSource = "";
    await inspect("AGENTS.md", async () => {
      agentsSource = (await this.store.raw("AGENTS.md")) ?? "";
      result.agents = await this.text("AGENTS.md", true);
    });
    const hidden = directDocuments(agentsSource);
    if (result.index)
      result.index.data.documents = result.index.data.documents.filter(
        (d) => !hidden.has(d.file.toLowerCase()),
      );
    const discovered = new Set(
      result.index?.data.documents.map((d) => d.file) ?? [],
    );
    const scan = async (relative: string) => {
      const dir = `.agents/docs${relative ? `/${relative}` : ""}`;
      try {
        for (const entry of await fs.readdir(await this.store.safePath(dir), {
          withFileTypes: true,
        })) {
          const file = relative ? `${relative}/${entry.name}` : entry.name;
          if (entry.isDirectory()) await scan(file);
          else if (
            entry.name.endsWith(".md") &&
            file.toLowerCase() !== "product.md"
          )
            discovered.add(file);
        }
      } catch (error) {
        if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
      }
    };
    await inspect(".agents/docs", () => scan(""));
    for (const file of [...discovered]
      .filter((f) => !hidden.has(f.toLowerCase()))
      .sort())
      await inspect(file, async () => {
        const doc = await this.text(file);
        result.files.push(doc);
        if (doc.content === null)
          result.diagnostics.push({ file, message: "索引引用的文件不存在" });
      });
    return result;
  }
  private async index(version: string | null) {
    const current = await this.store.read(DOC_INDEX, documentIndexSchema);
    if ((current?.version ?? null) !== version)
      throw new AppError("文档目录已变化，请重新加载后保存", 409);
    const index = current?.data ?? emptyIndex();
    const hidden = directDocuments((await this.store.raw("AGENTS.md")) ?? "");
    index.documents = index.documents.filter(
      (d) => !hidden.has(d.file.toLowerCase()),
    );
    return index;
  }
  category(name: string, id: string | undefined, version: string | null) {
    return this.store.serial(async () => {
      const index = await this.index(version);
      const category = parse(categorySchema, {
        id: id ?? `category-${randomUUID().slice(0, 8)}`,
        name,
      });
      if (id && !index.categories.some((c) => c.id === id))
        throw new AppError("类别不存在", 404);
      index.categories = id
        ? index.categories.map((c) => (c.id === id ? category : c))
        : [...index.categories, category];
      await this.store.json(
        DOC_INDEX,
        parse(documentIndexSchema, index),
        version,
      );
    });
  }
  saveAgents(content: string, version: string | null) {
    return this.store.serial(async () => {
      const source = await this.store.raw("AGENTS.md");
      if (source === null)
        throw new AppError("请先运行 init 准备 AGENTS.md 用户区域", 409);
      const updated = replaceAgentsUserContent(source, content);
      await this.store.write("AGENTS.md", updated, version);
      const index = await this.store.read(DOC_INDEX, documentIndexSchema);
      if (index) {
        const hidden = directDocuments(updated);
        const documents = index.data.documents.filter(
          (d) => !hidden.has(d.file.toLowerCase()),
        );
        if (documents.length !== index.data.documents.length)
          await this.store.json(
            DOC_INDEX,
            { ...index.data, documents },
            index.version,
          );
      }
    });
  }
  save(
    file: string,
    content: string,
    version: string | null,
    metadata: unknown,
    indexVersion: string | null,
  ) {
    return this.store.serial(async () => {
      const entry = parse(documentSchema, metadata);
      if (
        directDocuments((await this.store.raw("AGENTS.md")) ?? "").has(
          file.toLowerCase(),
        )
      )
        throw new AppError(
          "该文档由 AGENTS.md 直接路由，不在文档视图中编辑或登记",
          403,
        );
      if (entry.file !== file) throw new AppError("文件路径不一致", 422);
      const index = await this.index(indexVersion);
      index.documents = [
        ...index.documents.filter((d) => d.file !== file),
        entry,
      ];
      const checked = parse(documentIndexSchema, index);
      const target = `.agents/docs/${parse(documentPathSchema, file)}`;
      await this.store.safePath(DOC_INDEX);
      await this.store.write(target, content, version);
      try {
        await this.store.json(DOC_INDEX, checked, indexVersion);
      } catch (error) {
        throw new AppError(
          `正文已保存，但索引未更新。请重新加载后补充登记：${(error as Error).message}`,
          409,
        );
      }
    });
  }
}
