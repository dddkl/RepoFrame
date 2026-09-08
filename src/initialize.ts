import { promises as fs } from "node:fs";
import { Store, STATE, GOALS } from "./store";
import path from "node:path";
import { createHash } from "node:crypto";

export async function initialize(root: string, templates: string) {
  const store = new Store(root);
  return store.serial(async () => {
    const changed: string[] = [];
    for (const dir of [".agents/docs", GOALS, ".agents/skills/repoframe-init"])
      await fs.mkdir(await store.safePath(dir), { recursive: true });
    if ((await store.raw(STATE)) === null) {
      await store.json(STATE, { mode: "default", activeGoal: null }, null);
      changed.push(STATE);
    }
    const route = await fs.readFile(path.join(templates, "AGENTS.md"), "utf8");
    const existing = await store.raw("AGENTS.md");
    if (existing === null) {
      await store.write("AGENTS.md", route, null);
      changed.push("AGENTS.md");
    } else if (!existing.includes("<!-- repoframe:start -->")) {
      await store.write(
        "AGENTS.md",
        `${existing.trimEnd()}\n\n${route}`,
        createHash("sha256").update(existing).digest("hex"),
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
    return { changed, hasPrd: (await store.raw("PRD.md")) !== null };
  });
}
