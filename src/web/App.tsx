import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  CheckIcon,
  CircleDotIcon,
  CopyIcon,
  FileTextIcon,
  FrameIcon,
  LayoutDashboardIcon,
  PauseIcon,
  PencilIcon,
  PlayIcon,
  PlusIcon,
  RefreshCwIcon,
  RocketIcon,
  TargetIcon,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster, toast } from "@/components/ui/toast";
import { api, useProject } from "./api";
import { GoalEditor, ProductEditor } from "./editors";
import {
  ProductFields,
  MarkdownContent,
  MarkdownTitle,
} from "./product-fields";
import { ModeControl, QuickStart } from "./quick-start";
import type { GoalFile, Mode, Snapshot } from "../shared/protocol";

const INIT_PROMPT =
  "请读取 .agents/skills/repoframe-init/SKILL.md，从 PRD.md 提炼稳定产品信息，向我展示并确认后写入 .agents/docs/product.json。";
const CONTINUE_PROMPT =
  "请读取 AGENTS.md 和 .agents/state.json，确认处于 default 模式后，读取当前目标文件及产品信息，根据已有进展继续推进当前目标，完成必要验证并记录真实结果。";
async function copy(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    toast.add({ title: "指令已复制", type: "success" });
  } catch {
    toast.add({ title: "复制失败，请检查浏览器剪贴板权限", type: "error" });
  }
}

function Navigation({
  page,
  navigate,
  snapshot,
  connected,
}: {
  connected: boolean;
  page: string;
  navigate: (page: string) => void;
  snapshot: Snapshot | null;
}) {
  const { setOpenMobile } = useSidebar();
  return (
    <Sidebar>
      <SidebarHeader className="px-5 py-6">
        <div className="flex items-center gap-3">
          <div className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <FrameIcon className="size-5" />
          </div>
          <span className="text-lg font-semibold tracking-tight">
            RepoFrame
          </span>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup className="px-3">
          <SidebarGroupLabel>工作空间</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {[
                { id: "start", label: "快速开始", icon: RocketIcon },
                { id: "project", label: "项目", icon: LayoutDashboardIcon },
                { id: "goals", label: "目标", icon: TargetIcon },
              ].map(({ id, label, icon: Icon }) => (
                <SidebarMenuItem key={id}>
                  <SidebarMenuButton
                    isActive={
                      page === id ||
                      (id === "goals" && page.startsWith("goals/"))
                    }
                    onClick={() => {
                      navigate(id);
                      setOpenMobile(false);
                    }}
                  >
                    <Icon />
                    <span>{label}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="gap-3 p-5">
        <Separator />
        <div className="flex items-center gap-2 text-sm">
          <Badge
            variant="outline"
            role="status"
            title={connected ? "本地已连接" : "正在重新连接"}
          >
            <CircleDotIcon data-icon="inline-start" />
            {connected ? "本地已连接" : "正在重新连接"}
          </Badge>
        </div>
        <p
          className="truncate text-xs text-muted-foreground"
          title={snapshot?.repo.path}
        >
          {snapshot?.repo.path || "正在连接…"}
        </p>
      </SidebarFooter>
    </Sidebar>
  );
}

export default function App() {
  const { snapshot, error, connected, refresh } = useProject();
  const [page, setPage] = useState(() => location.hash.slice(1) || "start");
  const [filter, setFilter] = useState("open");
  const [busy, setBusy] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    contentRef.current?.scrollTo({ top: 0, left: 0, behavior: "instant" });
  }, [page]);
  const [goalEditor, setGoalEditor] = useState<{
    original: GoalFile | null;
    key: string;
  } | null>(null);
  const [productEditor, setProductEditor] = useState<NonNullable<
    Snapshot["product"]
  > | null>(null);
  const navigate = (next: string) => {
    location.hash = next;
    setPage(next);
  };
  useEffect(() => {
    const changed = () => setPage(location.hash.slice(1) || "start");
    window.addEventListener("hashchange", changed);
    return () => window.removeEventListener("hashchange", changed);
  }, []);
  const activeId = snapshot?.state?.data.activeGoal;
  const detail = page.startsWith("goals/")
    ? snapshot?.goals.find((g) => g.id === page.slice(6))
    : null;
  const mode = snapshot?.state?.data.mode;
  const canWrite = !!snapshot?.state && !busy && connected;
  const run = async (operation: () => Promise<unknown>, message: string) => {
    setBusy(true);
    try {
      await operation();
      toast.add({ title: message, type: "success" });
    } catch (error) {
      toast.add({
        title: "操作未完成",
        description: (error as Error).message,
        type: "error",
      });
    } finally {
      await refresh();
      setBusy(false);
    }
  };
  const action = (goal: GoalFile, name: "activate" | "pause" | "complete") =>
    void run(
      () =>
        api(`/goals/${goal.id}/${name}`, "POST", {
          version: goal.version,
          stateVersion: snapshot?.state?.version,
        }),
      name === "activate"
        ? "目标已启用，当前处于正常开发"
        : name === "pause"
          ? "目标已暂停，进展已保留"
          : "目标已完成",
    );
  const changeMode = (next: Mode) =>
    void run(
      () =>
        api("/state/mode", "PUT", {
          mode: next,
          version: snapshot?.state?.version,
        }),
      next === "iteration" ? "已切换到小步迭代" : "已切换到正常开发",
    );
  const pauseMissing = () =>
    void run(
      () =>
        api(`/goals/${activeId}/pause`, "POST", {
          stateVersion: snapshot?.state?.version,
        }),
      "已清除失效的当前目标引用",
    );
  const newGoal = () => setGoalEditor({ original: null, key: "new" });
  const actions = (goal: GoalFile) => (
    <div className="flex flex-wrap gap-2">
      <Button
        variant="outline"
        disabled={!canWrite}
        onClick={() => setGoalEditor({ original: goal, key: goal.version })}
      >
        <PencilIcon data-icon="inline-start" />
        编辑目标
      </Button>
      {goal.id === activeId ? (
        <Button
          key="pause"
          variant="outline"
          disabled={!canWrite}
          onClick={() => action(goal, "pause")}
        >
          <PauseIcon data-icon="inline-start" />
          暂停目标
        </Button>
      ) : (
        <Button
          key="activate"
          disabled={!canWrite}
          onClick={() => action(goal, "activate")}
        >
          <PlayIcon data-icon="inline-start" />
          {goal.data.status === "completed" ? "重新启用" : "启用目标"}
        </Button>
      )}
      {goal.data.status === "open" && (
        <Button
          key="complete"
          variant="outline"
          disabled={!canWrite}
          onClick={() => action(goal, "complete")}
        >
          <CheckIcon data-icon="inline-start" />
          完成目标
        </Button>
      )}
    </div>
  );

  return (
    <TooltipProvider>
      <Toaster>
        <SidebarProvider
          className="h-dvh min-h-0 overflow-hidden"
          style={{ "--sidebar-width": "15rem" } as React.CSSProperties}
        >
          <Navigation
            page={page}
            navigate={navigate}
            snapshot={snapshot}
            connected={connected}
          />
          <SidebarInset className="h-dvh min-h-0 min-w-0 overflow-hidden">
            <header className="flex h-16 shrink-0 items-center justify-between gap-3 px-5 md:px-10">
              <div className="flex min-w-0 items-center gap-3">
                <SidebarTrigger />
                <span className="truncate text-sm text-muted-foreground">
                  <span className="hidden sm:inline">
                    工作空间 <span className="mx-2">/</span>{" "}
                  </span>
                  {page === "start"
                    ? "快速开始"
                    : page === "project"
                      ? "项目"
                      : "目标"}
                </span>
              </div>
              <ModeControl
                compact
                mode={mode}
                activeGoal={activeId}
                disabled={!canWrite}
                change={changeMode}
              />
            </header>
            <Separator />
            <div
              ref={contentRef}
              role="region"
              aria-label="页面内容"
              tabIndex={0}
              className="min-h-0 flex-1 overflow-y-auto overscroll-contain [scrollbar-gutter:stable]"
            >
              <div className="mx-auto flex w-full max-w-6xl flex-col gap-7 px-5 py-8 md:px-10 md:py-10">
                {error && (
                  <Alert variant="destructive">
                    <AlertTitle>无法读取项目</AlertTitle>
                    <AlertDescription>
                      {error}
                      <Button variant="link" onClick={() => void refresh()}>
                        重试
                      </Button>
                    </AlertDescription>
                  </Alert>
                )}
                {!connected && snapshot && (
                  <Alert>
                    <AlertTitle>本地连接已断开</AlertTitle>
                    <AlertDescription>
                      正在尝试重新连接。连接恢复前暂停操作，请确认本地服务仍在运行。
                    </AlertDescription>
                  </Alert>
                )}
                {!snapshot ? (
                  <div aria-label="正在加载" className="flex flex-col gap-6">
                    <Skeleton className="h-10 w-48" />
                    <Skeleton className="h-48 w-full" />
                    <Skeleton className="h-64 w-full" />
                  </div>
                ) : (
                  <>
                    {snapshot.diagnostics
                      .filter(
                        (d) =>
                          !(
                            d.file === ".agents/docs/product.json" &&
                            d.message.startsWith("产品信息尚未确认")
                          ),
                      )
                      .map((diagnostic) => (
                        <Alert variant="destructive" key={diagnostic.file}>
                          <AlertTitle>{diagnostic.message}</AlertTitle>
                          <AlertDescription>{diagnostic.file}</AlertDescription>
                        </Alert>
                      ))}
                    {page === "start" ? (
                      <QuickStart
                        snapshot={snapshot}
                        disabled={!canWrite}
                        changeMode={changeMode}
                        navigate={navigate}
                        action={action}
                        pauseMissing={pauseMissing}
                      />
                    ) : page === "project" ? (
                      <>
                        <div className="flex flex-wrap items-start justify-between gap-4">
                          <div className="flex flex-col gap-2">
                            <p className="text-xs text-muted-foreground">
                              项目概览
                            </p>
                            <h1>{snapshot.repo.name}</h1>
                            <p className="text-sm text-muted-foreground">
                              让 Agent 清楚项目方向，也清楚这一次该如何工作。
                            </p>
                          </div>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => void refresh()}
                          >
                            <RefreshCwIcon data-icon="inline-start" />
                            刷新
                          </Button>
                        </div>
                        <div className="flex flex-col gap-7">
                          <Card>
                            <CardHeader>
                              <CardTitle>产品信息</CardTitle>
                              {snapshot.product && (
                                <CardAction className="flex items-center gap-2">
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    aria-label="编辑产品信息"
                                    disabled={!canWrite}
                                    onClick={() => {
                                      setProductEditor(snapshot.product);
                                    }}
                                  >
                                    <PencilIcon data-icon="inline-start" />
                                  </Button>
                                </CardAction>
                              )}
                            </CardHeader>
                            <CardContent className="flex flex-col gap-6">
                              {snapshot.product ? (
                                <ProductFields
                                  product={snapshot.product.data}
                                />
                              ) : (
                                <Empty>
                                  <EmptyHeader>
                                    <EmptyMedia variant="icon">
                                      <FileTextIcon />
                                    </EmptyMedia>
                                    <EmptyTitle>先确认产品方向</EmptyTitle>
                                    <EmptyDescription>
                                      准备 PRD，让现有 Agent
                                      提炼产品信息。确认一次，后续开发持续使用。
                                    </EmptyDescription>
                                  </EmptyHeader>
                                  <EmptyContent>
                                    <Button
                                      variant="outline"
                                      onClick={() => void copy(INIT_PROMPT)}
                                    >
                                      <CopyIcon data-icon="inline-start" />
                                      复制初始化指令
                                    </Button>
                                  </EmptyContent>
                                </Empty>
                              )}
                            </CardContent>
                            {!snapshot.product && (
                              <CardFooter>
                                <p className="text-xs text-muted-foreground">
                                  先运行 repoframe init 准备目录与初始化 Skill。
                                </p>
                              </CardFooter>
                            )}
                          </Card>
                        </div>
                      </>
                    ) : detail ? (
                      <>
                        <Button
                          variant="ghost"
                          className="self-start"
                          onClick={() => navigate("goals")}
                        >
                          <ArrowLeftIcon data-icon="inline-start" />
                          返回目标
                        </Button>
                        <div className="flex flex-col gap-3">
                          <div className="flex flex-wrap gap-2">
                            <Badge
                              variant={
                                detail.id === activeId ? "default" : "secondary"
                              }
                            >
                              {detail.id === activeId
                                ? "当前目标"
                                : detail.data.status === "completed"
                                  ? "已完成"
                                  : "未启用"}
                            </Badge>
                            <span className="text-xs text-muted-foreground">
                              {detail.id}
                            </span>
                          </div>
                          <h1 className="break-words">
                            <MarkdownTitle value={detail.data.title} />
                          </h1>
                          <MarkdownContent value={detail.data.objective} />
                        </div>
                        {actions(detail)}
                        {detail.id === activeId && (
                          <Alert>
                            <AlertTitle>让 Agent 接着推进</AlertTitle>
                            <AlertDescription>
                              <div className="flex flex-wrap items-center gap-3">
                                <span>
                                  复制指令交给现有 Agent，继续当前目标。
                                </span>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => void copy(CONTINUE_PROMPT)}
                                >
                                  <CopyIcon data-icon="inline-start" />
                                  复制继续指令
                                </Button>
                              </div>
                            </AlertDescription>
                          </Alert>
                        )}
                        <div className="grid items-start gap-6 lg:grid-cols-2">
                          <Card>
                            <CardHeader>
                              <CardTitle>完成条件</CardTitle>
                            </CardHeader>
                            <CardContent>
                              <MarkdownContent value={detail.data.doneWhen} />
                            </CardContent>
                          </Card>
                          <Card>
                            <CardHeader>
                              <CardTitle>任务约束</CardTitle>
                            </CardHeader>
                            <CardContent>
                              <MarkdownContent
                                value={detail.data.constraints}
                                empty="未设置额外任务约束"
                              />
                            </CardContent>
                          </Card>
                        </div>
                        <Card>
                          <CardHeader>
                            <CardTitle>进展记录</CardTitle>
                          </CardHeader>
                          <CardContent>
                            {detail.data.progress.trim() ? (
                              <MarkdownContent value={detail.data.progress} />
                            ) : (
                              <Empty>
                                <EmptyHeader>
                                  <EmptyTitle>等待第一条进展</EmptyTitle>
                                  <EmptyDescription>
                                    推进任务后，由 Agent 或你记录真实完成内容。
                                  </EmptyDescription>
                                </EmptyHeader>
                              </Empty>
                            )}
                          </CardContent>
                        </Card>
                        {Object.entries(detail.data)
                          .filter(
                            ([key]) =>
                              ![
                                "title",
                                "objective",
                                "doneWhen",
                                "constraints",
                                "progress",
                                "status",
                              ].includes(key),
                          )
                          .map(([key, value]) => (
                            <Card key={key}>
                              <CardHeader>
                                <CardTitle>{key}</CardTitle>
                              </CardHeader>
                              <CardContent>
                                <MarkdownContent value={value} />
                              </CardContent>
                            </Card>
                          ))}
                      </>
                    ) : page.startsWith("goals/") ? (
                      <Empty>
                        <EmptyHeader>
                          <EmptyTitle>目标不存在或暂时无法读取</EmptyTitle>
                          <EmptyDescription>
                            文件可能已被外部修改，请检查上方诊断。
                          </EmptyDescription>
                        </EmptyHeader>
                        <EmptyContent>
                          <Button
                            variant="outline"
                            onClick={() => navigate("goals")}
                          >
                            返回目标列表
                          </Button>
                        </EmptyContent>
                      </Empty>
                    ) : (
                      <>
                        <div className="flex flex-wrap items-start justify-between gap-4">
                          <div className="flex flex-col gap-2">
                            <p className="text-xs text-muted-foreground">
                              按需推进
                            </p>
                            <h1>复杂任务目标</h1>
                          </div>
                          <Button disabled={!canWrite} onClick={newGoal}>
                            <PlusIcon data-icon="inline-start" />
                            创建目标
                          </Button>
                        </div>
                        <ToggleGroup
                          aria-label="目标筛选"
                          variant="outline"
                          value={[filter]}
                          onValueChange={(values) => {
                            if (values[0]) setFilter(values[0]);
                          }}
                        >
                          <ToggleGroupItem value="open">
                            未完成（
                            {
                              snapshot.goals.filter(
                                (g) => g.data.status === "open",
                              ).length
                            }
                            ）
                          </ToggleGroupItem>
                          <ToggleGroupItem value="completed">
                            已完成（
                            {
                              snapshot.goals.filter(
                                (g) => g.data.status === "completed",
                              ).length
                            }
                            ）
                          </ToggleGroupItem>
                        </ToggleGroup>
                        <div className="flex flex-col gap-4">
                          {snapshot.goals.filter(
                            (g) => g.data.status === filter,
                          ).length ? (
                            snapshot.goals
                              .filter((g) => g.data.status === filter)
                              .map((goal) => (
                                <Card key={goal.id}>
                                  <CardHeader>
                                    <CardTitle>
                                      <Button
                                        variant="link"
                                        className="h-auto max-w-full justify-start p-0 whitespace-normal text-left"
                                        onClick={() =>
                                          navigate(`goals/${goal.id}`)
                                        }
                                      >
                                        <MarkdownTitle
                                          value={goal.data.title}
                                        />
                                      </Button>
                                    </CardTitle>
                                    <CardDescription>
                                      <MarkdownContent
                                        value={goal.data.objective}
                                      />
                                    </CardDescription>
                                    <CardAction>
                                      <Badge
                                        variant={
                                          goal.id === activeId
                                            ? "default"
                                            : "secondary"
                                        }
                                      >
                                        {goal.id === activeId
                                          ? "当前目标"
                                          : goal.data.status === "completed"
                                            ? "已完成"
                                            : "未启用"}
                                      </Badge>
                                    </CardAction>
                                  </CardHeader>
                                  <CardContent>
                                    <p className="text-xs text-muted-foreground">
                                      {goal.data.progress.trim()
                                        ? "已记录进展"
                                        : "尚无进展记录"}
                                    </p>
                                  </CardContent>
                                  <CardFooter className="flex-wrap justify-between gap-3">
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      onClick={() =>
                                        navigate(`goals/${goal.id}`)
                                      }
                                    >
                                      查看详情
                                      <ArrowRightIcon data-icon="inline-end" />
                                    </Button>
                                    {actions(goal)}
                                  </CardFooter>
                                </Card>
                              ))
                          ) : (
                            <Empty className="min-h-72">
                              <EmptyHeader>
                                <EmptyMedia variant="icon">
                                  <TargetIcon />
                                </EmptyMedia>
                                <EmptyTitle>
                                  {filter === "open"
                                    ? "需要持续推进时，再创建目标"
                                    : "还没有已完成的目标"}
                                </EmptyTitle>
                                <EmptyDescription>
                                  {filter === "open"
                                    ? "日常开发只需要选择模式。遇到复杂任务，再记录目的、完成条件和进展。"
                                    : "目标完成后会保留在这里，可以随时查看或重新启用。"}
                                </EmptyDescription>
                              </EmptyHeader>
                              {filter === "open" && (
                                <EmptyContent>
                                  <Button
                                    variant="outline"
                                    disabled={!canWrite}
                                    onClick={newGoal}
                                  >
                                    <PlusIcon data-icon="inline-start" />
                                    创建目标
                                  </Button>
                                </EmptyContent>
                              )}
                            </Empty>
                          )}
                        </div>
                        <p className="text-xs leading-relaxed text-muted-foreground">
                          启用目标会进入正常开发。先暂停或完成当前目标，才能切换到小步迭代。
                        </p>
                      </>
                    )}
                  </>
                )}
              </div>
            </div>
          </SidebarInset>
          {snapshot && goalEditor && (
            <GoalEditor
              key={goalEditor.key}
              original={goalEditor.original}
              snapshot={snapshot}
              close={() => setGoalEditor(null)}
              saved={async (id) => {
                await refresh();
                if (id) navigate(`goals/${id}`);
              }}
              reload={() => {
                const latest = snapshot.goals.find(
                  (g) => g.id === goalEditor.original?.id,
                );
                if (latest)
                  setGoalEditor({ original: latest, key: latest.version });
                else setGoalEditor(null);
              }}
            />
          )}
          {snapshot && productEditor && (
            <ProductEditor
              key={productEditor.version}
              original={productEditor}
              snapshot={snapshot}
              close={() => setProductEditor(null)}
              saved={refresh}
              reload={() => setProductEditor(snapshot.product)}
            />
          )}
        </SidebarProvider>
      </Toaster>
    </TooltipProvider>
  );
}
