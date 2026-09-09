import { directDocuments } from "./agents-document";
import { createHash, randomUUID } from "node:crypto";
import { promises as fs } from "node:fs";
import path from "node:path";
import { Store, GOALS } from "./store";
import {
  goalReadSchema,
  idSchema,
  legacyMarkdown,
  parse,
} from "./shared/protocol";
import { documentIndexSchema } from "./shared/documents";
import { emptyProgress, type Progress } from "./shared/progress";

export const PROGRESS_GUIDE = "repoframe-goal-progress.md";
export const PROGRESS_ROUTE =
  "执行或恢复目标，以及修改目标进展前，先读取 `.agents/docs/repoframe-goal-progress.md`，按其中的格式和维护规则更新 `progress`；仅查看目标时无需修改进展。";
export async function initializeProgress(
  store: Store,
  templates: string,
  changed: string[],
) {
  const guide = `.agents/docs/${PROGRESS_GUIDE}`;
  if ((await store.raw(guide)) === null) {
    await store.write(
      guide,
      await fs.readFile(path.join(templates, PROGRESS_GUIDE), "utf8"),
      null,
    );
    changed.push(guide);
  }
  const indexPath = ".agents/docs/index.json";
  const index = await store.read(indexPath, documentIndexSchema);
  if (index) {
    const hidden = directDocuments((await store.raw("AGENTS.md")) ?? "");
    const documents = index.data.documents.filter(
      (d) => !hidden.has(d.file.toLowerCase()),
    );
    if (documents.length !== index.data.documents.length) {
      await store.json(indexPath, { ...index.data, documents }, index.version);
      if (!changed.includes(indexPath)) changed.push(indexPath);
    }
  }
  const route = await store.raw("AGENTS.md");
  if (route) {
    const updated = route.replace(
      /<!-- repoframe:start -->[\s\S]*?<!-- repoframe:end -->/,
      (block) => {
        let next = block.replace(
          "目标文件的字段值统一使用字符串；内容以 Markdown 编写，列表也写在字符串中。",
          "目标内容字段使用 Markdown 字符串，`progress` 使用结构化执行路径。",
        );
        if (!next.includes(PROGRESS_GUIDE))
          next = next.replace(
            "<!-- repoframe:end -->",
            `${PROGRESS_ROUTE}\n\n<!-- repoframe:end -->`,
          );
        return next;
      },
    );
    if (updated !== route) {
      await store.write(
        "AGENTS.md",
        updated,
        createHash("sha256").update(route).digest("hex"),
      );
      if (!changed.includes("AGENTS.md")) changed.push("AGENTS.md");
    }
  }
  for (const entry of await fs.readdir(await store.safePath(GOALS))) {
    if (
      !entry.endsWith(".json") ||
      !idSchema.safeParse(entry.slice(0, -5)).success
    )
      continue;
    const file = `${GOALS}/${entry}`;
    try {
      const source = await store.raw(file);
      if (source === null) continue;
      const old = JSON.parse(source.replace(/^\uFEFF/, ""));
      if (
        typeof old.progress !== "string" &&
        !(
          Array.isArray(old.progress) &&
          old.progress.every((v: unknown) => typeof v === "string")
        )
      )
        continue;
      const text = legacyMarkdown(old.progress);
      const completed = old.status === "completed";
      const progress: Progress = text.trim()
        ? {
            current: completed ? 1 : 0,
            nodes: [
              {
                id: 0,
                kind: "start",
                title: "导入历史进展",
                previous: [],
                status: "done",
                message: text,
              },
              {
                id: 1,
                kind: "end",
                title: "目标完成",
                previous: [0],
                status: completed ? "done" : "planned",
                message: completed
                  ? "保留原目标的已完成状态，未重新执行验证"
                  : "",
              },
            ],
          }
        : emptyProgress();
      const data = parse(goalReadSchema, { ...old, progress });
      const backup = `.agents/backups/progress-${randomUUID()}/${entry}`;
      await store.write(backup, source, null);
      await store.json(
        file,
        data,
        createHash("sha256").update(source).digest("hex"),
      );
      changed.push(`${file}（原文备份：${backup}）`);
    } catch (error) {
      console.error(`跳过目标迁移 ${file}：${(error as Error).message}`);
    }
  }
}
