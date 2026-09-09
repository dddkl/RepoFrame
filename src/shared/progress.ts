import { z } from "zod";

const nodeId = z.number().int().nonnegative().max(Number.MAX_SAFE_INTEGER);
export const progressNodeSchema = z
  .object({
    id: nodeId,
    kind: z.enum(["start", "end"]).optional(),
    title: z.string().trim().min(1),
    previous: z.array(nodeId),
    status: z.enum(["planned", "active", "done", "abandoned"]),
    message: z.string(),
  })
  .strict();
export type ProgressNode = z.infer<typeof progressNodeSchema>;
export type Progress = { current: number | null; nodes: ProgressNode[] };
export const emptyProgress = (): Progress => ({ current: null, nodes: [] });

export function orderedNodes(nodes: ProgressNode[]) {
  const pending = new Set(nodes.map((n) => n.id));
  const result: ProgressNode[] = [];
  while (pending.size) {
    const next = nodes.find(
      (n) => pending.has(n.id) && n.previous.every((id) => !pending.has(id)),
    );
    if (!next) return [];
    pending.delete(next.id);
    result.push(next);
  }
  return result;
}
export const progressSchema = z
  .object({ current: nodeId.nullable(), nodes: z.array(progressNodeSchema) })
  .strict()
  .superRefine((graph, ctx) => {
    const fail = (message: string) => ctx.addIssue({ code: "custom", message });
    if (!graph.nodes.length) {
      if (graph.current !== null) fail("空路径的当前位置必须为空");
      return;
    }
    const byId = new Map(graph.nodes.map((n) => [n.id, n]));
    if (byId.size !== graph.nodes.length) {
      fail("节点 ID 不能重复");
      return;
    }
    if (
      graph.current === null ||
      !byId.has(graph.current) ||
      byId.get(graph.current)?.status === "abandoned"
    )
      fail("当前位置必须指向有效且未放弃的节点");
    const starts = graph.nodes.filter((n) => n.kind === "start"),
      ends = graph.nodes.filter((n) => n.kind === "end");
    if (starts.length !== 1 || ends.length !== 1) {
      fail("路径必须各有一个开始和结束节点");
      return;
    }
    if (starts[0].previous.length) fail("开始节点不能有前序");
    if (graph.nodes.some((n) => n.previous.includes(ends[0].id)))
      fail("结束节点不能有后续节点；追加工作时先将旧结束节点改为普通节点");
    for (const n of graph.nodes) {
      if (
        n.previous.some((id) => !byId.has(id)) ||
        new Set(n.previous).size !== n.previous.length
      ) {
        fail(`节点 ${n.id} 的前序引用无效或重复`);
        return;
      }
      if (n.status === "done" ? !n.message.trim() : n.message !== "")
        fail(`节点 ${n.id}：完成后必须填写结果，其他状态的消息必须为空`);
      if (
        (n.status === "active" || n.status === "done") &&
        n.previous.some((id) => byId.get(id)?.status !== "done")
      )
        fail(`节点 ${n.id} 的前序尚未全部完成`);
    }
    const order = orderedNodes(graph.nodes);
    if (order.length !== graph.nodes.length) {
      fail("路径不能成环");
      return;
    }
    const reached = new Set([starts[0].id]);
    for (const n of order)
      if (n.previous.some((id) => reached.has(id))) reached.add(n.id);
    if (reached.size !== graph.nodes.length)
      fail("所有节点必须能从开始节点到达");
    const toEnd = new Set([ends[0].id]);
    for (const n of [...order].reverse())
      if (toEnd.has(n.id) && n.status !== "abandoned")
        n.previous.forEach((id) => toEnd.add(id));
    const historical = new Set(
      graph.nodes.filter((n) => n.status === "abandoned").map((n) => n.id),
    );
    for (const n of [...order].reverse())
      if (historical.has(n.id)) n.previous.forEach((id) => historical.add(id));
    for (const n of graph.nodes)
      if (
        !toEnd.has(n.id) &&
        !(
          n.status === "abandoned" ||
          (n.status === "done" && historical.has(n.id))
        )
      )
        fail(`节点 ${n.id} 缺少通向结束的后续计划`);
  });

export function summaryNodes(progress: Progress) {
  const order = orderedNodes(progress.nodes);
  const current = order.find((n) => n.id === progress.current);
  if (!current) return { nodes: [], hidden: 0 };
  const neighbors = order.filter(
    (n) =>
      n.id !== current.id &&
      (current.previous.includes(n.id) ||
        n.previous.includes(current.id) ||
        n.status === "active"),
  );
  const selected = new Set([
    current.id,
    ...neighbors.slice(0, 6).map((n) => n.id),
  ]);
  return {
    nodes: order.filter((n) => selected.has(n.id)),
    hidden: Math.max(0, neighbors.length - 6),
  };
}
