import {
  ArrowRightIcon,
  CheckIcon,
  FrameIcon,
  FolderCodeIcon,
  TargetIcon,
  ZapIcon,
} from "lucide-react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardAction,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  Empty,
  EmptyHeader,
  EmptyTitle,
  EmptyContent,
  EmptyMedia,
} from "@/components/ui/empty";
import { cn } from "@/lib/utils";
import type { GoalFile, Mode, Snapshot } from "../shared/protocol";

export function ModeControl({
  mode,
  activeGoal,
  disabled,
  change,
  compact = false,
}: {
  mode?: Mode;
  activeGoal?: string | null;
  disabled: boolean;
  change: (mode: Mode) => void;
  compact?: boolean;
}) {
  return (
    <ToggleGroup
      aria-label={compact ? "全局开发模式" : "开发模式"}
      variant="outline"
      size={compact ? "sm" : "lg"}
      spacing={compact ? 0 : 2}
      className={cn(!compact && "w-full items-stretch")}
      value={mode ? [mode] : []}
      onValueChange={(values) => {
        const next = values[0];
        if ((next === "default" || next === "iteration") && next !== mode)
          change(next);
      }}
    >
      <ToggleGroupItem
        value="default"
        disabled={disabled}
        aria-label="正常开发"
        className={cn(
          !compact && "relative h-28 min-w-0 flex-1 flex-col gap-3",
        )}
      >
        {!compact && (
          <>
            <FrameIcon data-icon="inline-start" />
            {mode === "default" && (
              <CheckIcon
                className="absolute right-3 top-3"
                aria-hidden="true"
              />
            )}
          </>
        )}
        正常开发
      </ToggleGroupItem>
      <ToggleGroupItem
        value="iteration"
        disabled={disabled || !!activeGoal}
        title={activeGoal ? "请先暂停或完成当前目标" : undefined}
        aria-label="小步迭代"
        className={cn(
          !compact && "relative h-28 min-w-0 flex-1 flex-col gap-3",
        )}
      >
        {!compact && <ZapIcon data-icon="inline-start" />}
        {!compact && mode === "iteration" && (
          <CheckIcon className="absolute right-3 top-3" aria-hidden="true" />
        )}
        小步迭代
      </ToggleGroupItem>
    </ToggleGroup>
  );
}

export function QuickStart({
  snapshot,
  disabled,
  changeMode,
  navigate,
  action,
  pauseMissing,
}: {
  snapshot: Snapshot;
  disabled: boolean;
  changeMode: (mode: Mode) => void;
  navigate: (page: string) => void;
  action: (goal: GoalFile, name: "pause" | "complete") => void;
  pauseMissing: () => void;
}) {
  const mode = snapshot.state?.data.mode;
  const activeId = snapshot.state?.data.activeGoal;
  const active = snapshot.goals.find((goal) => goal.id === activeId);
  return (
    <div className="flex w-full max-w-5xl flex-col gap-8 self-center py-2 md:py-6">
      <div className="flex min-w-0 items-center gap-4">
        <div className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-muted text-muted-foreground">
          <FolderCodeIcon className="size-6" />
        </div>
        <h1 className="break-words">{snapshot.repo.name}</h1>
      </div>
      <div className="grid items-stretch gap-5 md:grid-cols-2">
        <Card
          className="[--card-spacing:--spacing(6)]"
          role="region"
          aria-label="开发模式面板"
        >
          <CardHeader>
            <CardTitle>开发模式</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-1 flex-col justify-center gap-4">
            <ModeControl
              mode={mode}
              activeGoal={activeId}
              disabled={disabled}
              change={changeMode}
            />
            {activeId && (
              <p className="text-sm text-muted-foreground">
                请先暂停或完成当前目标，再切换到小步迭代。
              </p>
            )}
          </CardContent>
        </Card>
        <Card
          className="[--card-spacing:--spacing(6)]"
          role="region"
          aria-label="当前目标面板"
        >
          <CardHeader>
            <CardTitle>当前目标</CardTitle>
            <CardAction>
              <Badge variant={activeId ? "default" : "secondary"}>
                {activeId ? "已启用" : "未启用"}
              </Badge>
            </CardAction>
          </CardHeader>
          <CardContent className="flex flex-1 flex-col justify-center gap-3">
            {active ? (
              <>
                <h2 className="break-words">{active.data.title}</h2>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {active.data.objective}
                </p>
              </>
            ) : (
              <Empty className="flex-row justify-start gap-3 p-0 text-left">
                <EmptyMedia variant="icon" className="mb-0">
                  <TargetIcon />
                </EmptyMedia>
                <EmptyHeader className="items-start">
                  <EmptyTitle>
                    {activeId ? "当前目标无法读取" : "尚未启用目标"}
                  </EmptyTitle>
                </EmptyHeader>
              </Empty>
            )}
          </CardContent>
          <CardFooter className="flex-wrap gap-2">
            {!active ? (
              <EmptyContent className="max-w-none items-start">
                {activeId ? (
                  <Button
                    variant="outline"
                    disabled={disabled}
                    onClick={pauseMissing}
                  >
                    暂停失效的当前目标
                  </Button>
                ) : (
                  <Button variant="outline" onClick={() => navigate("goals")}>
                    选择目标
                    <ArrowRightIcon data-icon="inline-end" />
                  </Button>
                )}
              </EmptyContent>
            ) : (
              <>
                <Button onClick={() => navigate(`goals/${active.id}`)}>
                  打开目标
                  <ArrowRightIcon data-icon="inline-end" />
                </Button>
                <Button
                  variant="outline"
                  disabled={disabled}
                  onClick={() => action(active, "pause")}
                >
                  暂停目标
                </Button>
                <Button
                  variant="outline"
                  disabled={disabled}
                  onClick={() => action(active, "complete")}
                >
                  完成目标
                </Button>
              </>
            )}
          </CardFooter>
        </Card>
      </div>
    </div>
  );
}
