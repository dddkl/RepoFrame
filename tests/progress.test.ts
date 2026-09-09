import { expect, it } from "vitest";
import { promises as fs } from "node:fs";
import path from "node:path";
import {
  progressSchema,
  summaryNodes,
  type Progress,
} from "../src/shared/progress";
import { initialize } from "../src/initialize";
import { Store } from "../src/store";

import { graph } from "./fixtures/progress";

it("支持转向、并行及完整汇合计划，摘要保留当前和直接邻居", () => {
  expect(progressSchema.safeParse(graph).success).toBe(true);
  expect(summaryNodes(graph).nodes.map((n) => n.id)).toEqual([0, 3, 4]);
  const many: Progress = {
    current: 0,
    nodes: [
      graph.nodes[0],
      ...Array.from({ length: 8 }, (_, i) => ({
        id: i + 1,
        title: `任务${i}`,
        previous: [0],
        status: "planned" as const,
        message: "",
      })),
      {
        id: 9,
        kind: "end",
        title: "完成",
        previous: [1, 2, 3, 4, 5, 6, 7, 8],
        status: "planned",
        message: "",
      },
    ],
  };
  expect(summaryNodes(many).nodes).toHaveLength(7);
  expect(summaryNodes(many).hidden).toBe(2);
});
it("拒绝语义字符串 ID、重复引用、环、缺失后续计划和虚假消息", () => {
  for (const mutate of [
    (g: any) => {
      g.nodes[1].id = "branch";
    },
    (g: any) => {
      g.nodes[1].id = 0;
    },
    (g: any) => {
      g.current = 99;
    },
    (g: any) => {
      g.nodes[4].previous = [2, 99];
    },
    (g: any) => {
      g.nodes[3].previous = [4];
    },
    (g: any) => {
      g.nodes[4].previous = [2];
    },
    (g: any) => {
      g.nodes[2].message = "";
    },
    (g: any) => {
      g.nodes[3].message = "正在实现";
    },
  ]) {
    const copy = structuredClone(graph);
    mutate(copy);
    expect(progressSchema.safeParse(copy).success).toBe(false);
  }
});
it("init 备份并迁移历史消息，幂等保留状态和规范编辑", async () => {
  const base = path.resolve(".tmp/progress-tests");
  await fs.mkdir(base, { recursive: true });
  const root = await fs.mkdtemp(path.join(base, "repo-"));
  try {
    await initialize(root, path.resolve("templates"));
    const store = new Store(root);
    const old = {
      title: "目标",
      objective: "目的",
      doneWhen: "验证",
      constraints: "",
      progress: "原始进展\n    缩进",
      status: "open",
    };
    await store.json(".agents/goals/old.json", old, null);
    const invalid = (await store.snapshot()).goals[0];
    expect(invalid.data.title).toBe("目标");
    expect(invalid.progressError).toContain("迁移");
    const state = await store.raw(".agents/state.json");
    const result = await initialize(root, path.resolve("templates"));
    expect(result.changed.some((s) => s.includes("备份"))).toBe(true);
    const goal = (await store.snapshot()).goals[0];
    expect(goal.data.progress.nodes[0].message).toBe(old.progress);
    expect(goal.data.progress.current).toBe(0);
    const source = await store.raw(".agents/goals/old.json");
    await fs.appendFile(
      path.join(root, ".agents/docs/repoframe-goal-progress.md"),
      "\n用户补充\n",
    );
    await initialize(root, path.resolve("templates"));
    expect(await store.raw(".agents/goals/old.json")).toBe(source);
    expect(await store.raw(".agents/state.json")).toBe(state);
    expect(
      await store.raw(".agents/docs/repoframe-goal-progress.md"),
    ).toContain("用户补充");
    const snapshot = await store.snapshot();
    await store.goalAction(
      "old",
      "complete",
      goal.version,
      snapshot.state!.version,
    );
    expect((await store.snapshot()).goals[0].data.progress).toEqual(
      goal.data.progress,
    );
  } finally {
    await fs.rm(root, { recursive: true, force: true });
  }
});
