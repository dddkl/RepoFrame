import { organizeAgents } from "./agents-document";
import { promises as fs } from "node:fs";
import { Store, STATE, GOALS } from "./store";
import path from "node:path";
import { createHash } from "node:crypto";
import { DOC_INDEX } from "./documents";
import { emptyIndex } from "./shared/documents";
import { initializeProgress } from "./progress-initialize";

export async function initialize(root: string, templates: string) {
  const store = new Store(root);
  return store.serial(async () => {
    const changed: string[] = [];
    if ((await store.raw(DOC_INDEX)) === null) {
      await store.json(DOC_INDEX, emptyIndex(), null);
      changed.push(DOC_INDEX);
    }
    for (const dir of [".agents/docs", GOALS, ".agents/skills/repoframe-init"])
      await fs.mkdir(await store.safePath(dir), { recursive: true });
    if ((await store.raw(STATE)) === null) {
      await store.json(STATE, { mode: "default", activeGoal: null }, null);
      changed.push(STATE);
    }
    const route = await fs.readFile(path.join(templates, "AGENTS.md"), "utf8");
    const existing = await store.raw("AGENTS.md");
    const organized = organizeAgents(existing, route);
    if (organized !== existing) {
      if (existing !== null)
        await store.write(
          ".agents/backups/agents-" + Date.now() + ".md",
          existing,
          null,
        );
      await store.write(
        "AGENTS.md",
        organized,
        existing === null
          ? null
          : createHash("sha256").update(existing).digest("hex"),
      );
      changed.push("AGENTS.md");
    }
    const skillPath = ".agents/skills/repoframe-init/SKILL.md";
    if ((await store.raw(skillPath)) === null) {
      await store.write(
        skillPath,
        await fs.readFile(
          path.join(templates, "repoframe-init", "SKILL.md"),
          "utf8",
        ),
        null,
      );
      changed.push(skillPath);
    }
    await initializeProgress(store, templates, changed);
    return { changed, hasPrd: (await store.raw("PRD.md")) !== null };
  });
}
