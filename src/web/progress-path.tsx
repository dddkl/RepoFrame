import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { ArrowLeftIcon, ArrowRightIcon, ChevronDownIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardAction,
} from "@/components/ui/card";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { Empty, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { MarkdownContent, MarkdownTitle } from "./product-fields";
import { orderedNodes, summaryNodes, type Progress } from "../shared/progress";
import type { GoalFile } from "../shared/protocol";

const labels = {
  planned: "待执行",
  active: "执行中",
  done: "已完成",
  abandoned: "已放弃",
};
function PathGraph({ progress, full }: { progress: Progress; full: boolean }) {
  const container = useRef<HTMLDivElement>(null);
  const currentRef = useRef<HTMLDivElement>(null);
  const positioned = useRef(false);
  const [points, setPoints] = useState<Record<number, number>>({});
  const [height, setHeight] = useState(0);
  const [open, setOpen] = useState<Set<number>>(
    () => new Set(progress.current === null ? [] : [progress.current]),
  );
  useEffect(() => {
    if (progress.current !== null)
      setOpen((old) => new Set([...old, progress.current!]));
  }, [progress.current]);
  const all = orderedNodes(progress.nodes);
  const summary = summaryNodes(progress);
  const nodes = full ? all : summary.nodes;
  const columns = new Map<number, number>();
  const children = new Map(
    all.map((n) => [
      n.id,
      all.filter((c) => c.previous.includes(n.id)).map((c) => c.id),
    ]),
  );
  const reserved = new Set<number>();
  for (const n of all) {
    const parents = n.previous.map((id) => columns.get(id) ?? 0);
    let lane = parents.length ? Math.min(...parents) : 0;
    if (n.previous.some((id) => children.get(id)?.indexOf(n.id)! > 0)) {
      lane = 0;
      while (reserved.has(lane)) lane++;
    }
    columns.set(n.id, lane);
    reserved.add(lane);
  }
  // Only allocate lanes present in this view; edges to omitted nodes stay omitted.
  const visibleLanes = [...new Set(nodes.map((n) => columns.get(n.id)!))].sort(
    (a, b) => a - b,
  );
  const x = (id: number) => 14 + visibleLanes.indexOf(columns.get(id)!) * 22;
  const width = Math.max(30, visibleLanes.length * 22 + 8);
  const highlight = new Set<number>();
  const byId = new Map(all.map((n) => [n.id, n]));
  const stack = progress.current === null ? [] : [progress.current];
  while (stack.length) {
    const id = stack.pop()!;
    if (highlight.has(id)) continue;
    highlight.add(id);
    byId.get(id)?.previous.forEach((p) => {
      if (byId.get(p)?.status === "done") stack.push(p);
    });
  }
  useLayoutEffect(() => {
    const element = container.current;
    if (!element) return;
    const measure = () => {
      const top = element.getBoundingClientRect().top;
      const next: Record<number, number> = {};
      element
        .querySelectorAll<HTMLElement>("[data-path-row]")
        .forEach((row) => {
          next[Number(row.dataset.pathRow)] =
            row.getBoundingClientRect().top - top + 22;
        });
      setPoints(next);
      setHeight(element.scrollHeight);
    };
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    element
      .querySelectorAll("[data-path-row]")
      .forEach((row) => observer.observe(row));
    measure();
    return () => observer.disconnect();
  }, [progress, full]);
  useLayoutEffect(() => {
    if (full && !positioned.current && height) {
      currentRef.current?.scrollIntoView({
        block: "center",
        behavior: "instant",
      });
      positioned.current = true;
    }
  }, [full, height]);
  return (
    <>
      <div className="max-w-full overflow-x-auto">
        <div
          ref={container}
          className="relative min-w-0"
          style={{ minWidth: width + 180 }}
        >
          <svg
            aria-hidden="true"
            width={width}
            height={height}
            className="pointer-events-none absolute top-0 left-0 text-foreground"
          >
            {nodes.flatMap((n) =>
              n.previous
                .filter(
                  (id) =>
                    points[id] !== undefined && points[n.id] !== undefined,
                )
                .map((id) => {
                  const abandoned =
                    n.status === "abandoned" ||
                    byId.get(id)?.status === "abandoned";
                  const future = n.status === "planned";
                  const strong = highlight.has(n.id) && highlight.has(id);
                  const a = points[id],
                    b = points[n.id];
                  return (
                    <path
                      key={`${id}-${n.id}`}
                      data-edge={`${id}-${n.id}`}
                      d={
                        n.previous.length > 1
                          ? `M ${x(id)} ${a} L ${x(id)} ${b - 24} C ${x(id)} ${b - 8}, ${x(n.id)} ${b - 16}, ${x(n.id)} ${b}`
                          : `M ${x(id)} ${a} C ${x(id)} ${a + 16}, ${x(n.id)} ${a + 8}, ${x(n.id)} ${a + 24} L ${x(n.id)} ${b}`
                      }
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={strong ? 2 : 1.5}
                      opacity={abandoned ? 0.15 : strong ? 0.85 : 0.3}
                      strokeDasharray={future ? "4 5" : undefined}
                    />
                  );
                }),
            )}
            {/* Opaque backing keeps muted nodes above every connecting edge. */}
            {nodes.map(n => points[n.id] !== undefined && (
              <circle
                key={`backing-${n.id}`}
                cx={x(n.id)}
                cy={points[n.id]}
                r={n.id === progress.current ? 8 : n.kind ? 6 : 4}
                className="fill-background"
              />
            ))}
            {nodes.map(
              (n) =>
                points[n.id] !== undefined && (
                  <g
                    key={n.id}
                    opacity={
                      n.status === "abandoned"
                        ? 0.25
                        : n.status === "planned"
                          ? 0.4
                          : 1
                    }
                  >
                    <circle
                      cx={x(n.id)}
                      cy={points[n.id]}
                      r={n.id === progress.current ? 8 : n.kind ? 6 : 4}
                      className={
                        n.id === progress.current
                          ? "fill-background"
                          : "fill-current"
                      }
                      stroke="currentColor"
                      strokeWidth={n.id === progress.current ? 2 : 1.5}
                    />
                    {n.id === progress.current && (
                      <circle
                        cx={x(n.id)}
                        cy={points[n.id]}
                        r={n.id === progress.current ? 3 : 3.5}
                        fill="currentColor"
                      />
                    )}
                  </g>
                ),
            )}
          </svg>
          <ol
            className="flex list-none flex-col gap-3"
            style={{ paddingLeft: width + 8 }}
          >
            {nodes.map((n) => (
              <li key={n.id}>
                <div
                  data-path-row={n.id}
                  ref={n.id === progress.current ? currentRef : undefined}
                  className={
                    n.status === "abandoned"
                      ? "flex flex-col gap-2 opacity-40"
                      : "flex flex-col gap-2"
                  }
                >
                  <div className="flex min-h-11 flex-wrap items-center gap-2">
                    {n.status === "done" ? (
                      <Button
                        variant="ghost"
                        className="h-auto min-h-8 min-w-0 justify-start whitespace-normal text-left"
                        aria-expanded={open.has(n.id)}
                        onClick={() =>
                          setOpen((old) => {
                            const next = new Set(old);
                            if (next.has(n.id)) next.delete(n.id);
                            else next.add(n.id);
                            return next;
                          })
                        }
                      >
                        <ChevronDownIcon
                          data-icon="inline-start"
                          className={open.has(n.id) ? "rotate-0" : "-rotate-90"}
                        />
                        {n.title}
                      </Button>
                    ) : (
                      <span className="py-2 text-sm font-medium">
                        {n.title}
                      </span>
                    )}
                    {n.id === progress.current && (
                      <Badge variant="outline">当前</Badge>
                    )}
                    <span className="text-xs text-muted-foreground">
                      {n.kind === "start"
                        ? "开始 · "
                        : n.kind === "end"
                          ? "结束 · "
                          : ""}
                      {labels[n.status]}
                    </span>
                  </div>
                  {n.status === "done" && open.has(n.id) && (
                    <div className="pb-4 pl-2 text-sm">
                      <MarkdownContent value={n.message} />
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </div>
      </div>
      {!full && summary.hidden > 0 && (
        <p className="text-xs text-muted-foreground">
          还有 {summary.hidden} 个相关节点，可在完整路径中查看。
        </p>
      )}
    </>
  );
}

export function ProgressPanel({
  goal,
  full = false,
  navigate,
}: {
  goal: GoalFile;
  full?: boolean;
  navigate: (page: string) => void;
}) {
  const progress = goal.data.progress;
  return (
    <Card
      className="min-w-0"
      role="region"
      aria-label={full ? "完整执行路径" : "进展摘要"}
    >
      <CardHeader>
        <CardTitle>{full ? "执行路径" : "进展记录"}</CardTitle>
        {!full && (
          <CardAction>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate(`goals/${goal.id}/progress`)}
            >
              查看完整路径
              <ArrowRightIcon data-icon="inline-end" />
            </Button>
          </CardAction>
        )}
      </CardHeader>
      <CardContent className="flex min-w-0 flex-col gap-4">
        {goal.progressError ? (
          <Alert variant="destructive">
            <AlertTitle>{goal.progressError}</AlertTitle>
          </Alert>
        ) : (
          <>
            {goal.data.status === "completed" &&
              progress.nodes.some(
                (n) => n.status === "planned" || n.status === "active",
              ) && (
                <Alert>
                  <AlertTitle>目标已完成，路径仍有未完成节点</AlertTitle>
                </Alert>
              )}
            {progress.nodes.length ? (
              <PathGraph
                key={`${goal.id}-${full}`}
                progress={progress}
                full={full}
              />
            ) : (
              <Empty>
                <EmptyHeader>
                  <EmptyTitle>尚未建立执行路径</EmptyTitle>
                </EmptyHeader>
              </Empty>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
export function FullProgress({
  goal,
  navigate,
}: {
  goal: GoalFile;
  navigate: (page: string) => void;
}) {
  return (
    <>
      <Button
        variant="ghost"
        className="self-start"
        onClick={() => navigate(`goals/${goal.id}`)}
      >
        <ArrowLeftIcon data-icon="inline-start" />
        返回目标详情
      </Button>
      <div className="flex items-center gap-3">
        <h1>
          <MarkdownTitle value={goal.data.title} />
        </h1>
        <Badge variant="secondary">
          {goal.data.status === "completed" ? "已完成" : "未完成"}
        </Badge>
      </div>
      <ProgressPanel goal={goal} full navigate={navigate} />
    </>
  );
}
