import { emptyProgress } from "../shared/progress";
import { useEffect, useState } from "react";
import { SaveIcon } from "lucide-react";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Field,
  FieldLabel,
  FieldGroup,
  FieldDescription,
  FieldError,
} from "@/components/ui/field";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { toast } from "@/components/ui/toast";
import { api } from "./api";

import {
  goalSchema,
  idSchema,
  type GoalFile,
  type Snapshot,
  type Goal,
} from "../shared/protocol";

type Errors = Record<string, string>;
function errorsFor(error: z.ZodError): Errors {
  return Object.fromEntries(
    error.issues.map((issue) => [String(issue.path[0]), issue.message]),
  );
}
export function useLeaveGuard(dirty: boolean) {
  useEffect(() => {
    const before = (event: BeforeUnloadEvent) => {
      if (dirty) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", before);
    return () => window.removeEventListener("beforeunload", before);
  }, [dirty]);
  return () =>
    !dirty || window.confirm("有尚未保存的修改，确定放弃这些修改吗？");
}

function TextField({
  name,
  label,
  value,
  change,
  error,
  multiline = false,
  description,
}: {
  name: string;
  label: string;
  value: string;
  change: (value: string) => void;
  error?: string;
  multiline?: boolean;
  description?: string;
}) {
  const Control = multiline ? Textarea : Input;
  return (
    <Field data-invalid={!!error}>
      <FieldLabel htmlFor={name}>{label}</FieldLabel>
      <Control
        id={name}
        value={typeof value === "string" ? value : ""}
        onChange={(event) => change(event.target.value)}
        aria-invalid={!!error}
        aria-describedby={error ? `${name}-error` : undefined}
      />
      {description && <FieldDescription>{description}</FieldDescription>}
      {error && <FieldError id={`${name}-error`}>{error}</FieldError>}
    </Field>
  );
}

function ChangedNotice({ onReload }: { onReload: () => void }) {
  return (
    <Alert>
      <AlertTitle>文件在编辑期间发生变化</AlertTitle>
      <AlertDescription>
        当前草稿已保留。保存前请重新加载最新内容。
        <Button type="button" variant="link" onClick={onReload}>
          重新加载
        </Button>
      </AlertDescription>
    </Alert>
  );
}

export function GoalEditor({
  original,
  snapshot,
  close,
  saved,
  reload,
}: {
  original: GoalFile | null;
  snapshot: Snapshot;
  close: () => void;
  saved: (id: string) => Promise<void>;
  reload: () => void;
}) {
  const initial: Goal = original?.data || {
    title: "",
    objective: "",
    doneWhen: "",
    constraints: "",
    progress: emptyProgress(),
    status: "open",
  };
  const [draft, setDraft] = useState<Goal>(structuredClone(initial));
  const [id, setId] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const canLeave = useLeaveGuard(
    JSON.stringify(draft) !== JSON.stringify(initial) || !!id,
  );
  const latest = original
    ? snapshot.goals.find((g) => g.id === original.id)
    : null;
  const changed = !!original && latest?.version !== original.version;
  const update = <K extends keyof Goal>(name: K, value: Goal[K]) =>
    setDraft({ ...draft, [name]: value });
  const submit = async (activate: boolean) => {
    const checked = goalSchema.safeParse(draft);
    const checkedId = id ? idSchema.safeParse(id) : null;
    if (!checked.success || checkedId?.success === false) {
      setErrors({
        ...(!checked.success ? errorsFor(checked.error) : {}),
        ...(checkedId?.success === false
          ? { id: checkedId.error.issues[0].message }
          : {}),
      });
      return;
    }
    setPending(true);
    setError("");
    setErrors({});
    try {
      let goalId = original?.id;
      if (original)
        await api(`/goals/${original.id}`, "PUT", {
          data: checked.data,
          version: original.version,
        });
      else
        goalId = (
          await api<{ id: string }>("/goals", "POST", {
            data: checked.data,
            id: id || undefined,
            activate,
            stateVersion: snapshot.state?.version,
          })
        ).id;
      toast.add({
        title: original
          ? "目标已保存"
          : activate
            ? "目标已创建并启用"
            : "目标已创建，尚未启用",
        type: "success",
      });
      await saved(goalId!);
      close();
    } catch (error) {
      setError((error as Error).message);
      await saved("");
    } finally {
      setPending(false);
    }
  };
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !pending && canLeave()) close();
      }}
    >
      <DialogContent className="max-h-[90svh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>
            {original ? "编辑目标" : "创建复杂任务目标"}
          </DialogTitle>
          {!original && (
            <DialogDescription>
              只在复杂、耗时较长的任务中使用。普通创建不会改变当前模式。
            </DialogDescription>
          )}
        </DialogHeader>
        <form
          id="goal-form"
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            void submit(false);
          }}
        >
          <fieldset disabled={pending} className="min-w-0">
            <FieldGroup>
              {changed && (
                <ChangedNotice
                  onReload={() => {
                    if (canLeave()) reload();
                  }}
                />
              )}
              {error && (
                <Alert variant="destructive">
                  <AlertTitle>未能保存</AlertTitle>
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}
              <TextField
                name="title"
                label="目标名称"
                value={draft.title}
                change={(value) => update("title", value)}
                error={errors.title}
              />
              {!original && (
                <TextField
                  name="id"
                  label="目标标识（可选）"
                  value={id}
                  change={setId}
                  error={errors.id}
                  description="留空自动生成；填写时使用小写字母、数字、连字符或下划线。"
                />
              )}
              <TextField
                name="objective"
                label="目标目的"
                value={draft.objective}
                change={(value) => update("objective", value)}
                error={errors.objective}
                multiline
              />
              <TextField
                multiline
                name="doneWhen"
                label="完成条件"
                value={draft.doneWhen}
                change={(value) => update("doneWhen", value)}
                error={errors.doneWhen}
              />
              <TextField
                multiline
                name="constraints"
                label="任务约束"
                value={draft.constraints}
                change={(value) => update("constraints", value)}
                error={errors.constraints}
              />
              {Object.entries(draft)
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
                .map(([key, value], index) => (
                  <TextField
                    key={key}
                    name={`goal-extra-${index}`}
                    label={key}
                    value={typeof value === "string" ? value : ""}
                    change={(text) => update(key, text)}
                    error={errors[key]}
                    multiline
                  />
                ))}
            </FieldGroup>
          </fieldset>
        </form>
        <DialogFooter>
          <Button
            variant="outline"
            disabled={pending}
            onClick={() => {
              if (canLeave()) close();
            }}
          >
            取消
          </Button>
          {!original && (
            <Button
              variant="outline"
              disabled={pending || !snapshot.state}
              onClick={() => void submit(true)}
            >
              创建并启用
            </Button>
          )}
          <Button
            type="submit"
            form="goal-form"
            disabled={pending || changed || !snapshot.state}
          >
            <SaveIcon data-icon="inline-start" />
            {pending ? "正在保存…" : original ? "保存目标" : "仅创建"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ProductEditor({
  original,
  snapshot,
  close,
  saved,
  reload,
}: {
  original: NonNullable<Snapshot["product"]>;
  snapshot: Snapshot;
  close: () => void;
  saved: () => Promise<void>;
  reload: () => void;
}) {
  const [draft, setDraft] = useState(original.data);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const canLeave = useLeaveGuard(draft !== original.data);
  const changed = (snapshot.product?.version ?? "") !== original.version;
  const finish = () => {
    if (!pending && canLeave()) close();
  };
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) finish();
      }}
    >
      <DialogContent
        className="flex max-h-[90dvh] flex-col sm:max-w-4xl"
        showCloseButton={!pending}
      >
        <DialogHeader>
          <DialogTitle>编辑产品信息</DialogTitle>
        </DialogHeader>
        <form
          className="flex min-h-0 flex-col gap-5"
          onSubmit={async (event) => {
            event.preventDefault();
            setPending(true);
            setError("");
            try {
              await api("/product", "PUT", {
                data: draft,
                version: original.version,
              });
              await saved();
              close();
              toast.add({ title: "产品信息已保存", type: "success" });
            } catch (error) {
              setError((error as Error).message);
              await saved();
            } finally {
              setPending(false);
            }
          }}
        >
          <div className="flex min-h-0 flex-col gap-4 overflow-y-auto px-1 [scrollbar-gutter:stable]">
            {changed && (
              <ChangedNotice
                onReload={() => {
                  if (canLeave()) reload();
                }}
              />
            )}
            {error && (
              <Alert variant="destructive">
                <AlertTitle>未能保存</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="product-markdown" className="sr-only">
                  产品 Markdown 正文
                </FieldLabel>
                <Textarea
                  id="product-markdown"
                  className="min-h-[50dvh]"
                  value={draft}
                  disabled={pending}
                  onChange={(e) => setDraft(e.target.value)}
                />
              </Field>
            </FieldGroup>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={pending}
              onClick={finish}
            >
              取消
            </Button>
            <Button type="submit" disabled={pending || changed}>
              <SaveIcon data-icon="inline-start" />
              {pending ? "正在保存…" : "保存产品信息"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
