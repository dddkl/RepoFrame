import { useEffect, useState } from "react";
import { PlusIcon, XIcon, SaveIcon } from "lucide-react";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  InputGroup,
  InputGroupInput,
  InputGroupAddon,
  InputGroupButton,
} from "@/components/ui/input-group";
import {
  Field,
  FieldLabel,
  FieldGroup,
  FieldDescription,
  FieldError,
  FieldSet,
  FieldLegend,
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
import { productFieldLabel } from "./product-fields";
import {
  goalSchema,
  productSchema,
  idSchema,
  type GoalFile,
  type Snapshot,
  type Product,
  type Goal,
} from "../shared/protocol";

type Errors = Record<string, string>;
function errorsFor(error: z.ZodError): Errors {
  return Object.fromEntries(
    error.issues.map((issue) => [String(issue.path[0]), issue.message]),
  );
}
function useLeaveGuard(dirty: boolean) {
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
        value={value}
        onChange={(event) => change(event.target.value)}
        aria-invalid={!!error}
        aria-describedby={error ? `${name}-error` : undefined}
      />
      {description && <FieldDescription>{description}</FieldDescription>}
      {error && <FieldError id={`${name}-error`}>{error}</FieldError>}
    </Field>
  );
}

function ListEditor({
  label,
  name,
  value,
  change,
  error,
}: {
  label: string;
  name: string;
  value: string[];
  change: (value: string[]) => void;
  error?: string;
}) {
  return (
    <FieldSet>
      <FieldLegend variant="label">{label}</FieldLegend>
      <FieldGroup className="gap-2">
        {value.map((item, index) => (
          <Field key={index} data-invalid={!!error}>
            <FieldLabel className="sr-only" htmlFor={`${name}-${index}`}>
              {label} {index + 1}
            </FieldLabel>
            <InputGroup>
              <InputGroupInput
                id={`${name}-${index}`}
                value={item}
                aria-invalid={!!error}
                onChange={(event) =>
                  change(
                    value.map((old, i) =>
                      i === index ? event.target.value : old,
                    ),
                  )
                }
              />
              <InputGroupAddon align="inline-end">
                <InputGroupButton
                  type="button"
                  size="icon-xs"
                  aria-label={`删除${label} ${index + 1}`}
                  onClick={() => change(value.filter((_, i) => i !== index))}
                >
                  <XIcon data-icon="inline-start" />
                </InputGroupButton>
              </InputGroupAddon>
            </InputGroup>
          </Field>
        ))}
        {error && <FieldError>{error}</FieldError>}
      </FieldGroup>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="self-start"
        onClick={() => change([...value, ""])}
      >
        <PlusIcon data-icon="inline-start" />
        添加{label}
      </Button>
    </FieldSet>
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
    doneWhen: [""],
    constraints: [],
    progress: [],
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
          <DialogDescription>
            {original
              ? "保留清晰的完成条件，让下一次执行能接着推进。"
              : "只在复杂、耗时较长的任务中使用。普通创建不会改变当前模式。"}
          </DialogDescription>
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
              <ListEditor
                name="doneWhen"
                label="完成条件"
                value={draft.doneWhen}
                change={(value) => update("doneWhen", value)}
                error={errors.doneWhen}
              />
              <ListEditor
                name="constraints"
                label="任务约束"
                value={draft.constraints}
                change={(value) => update("constraints", value)}
                error={errors.constraints}
              />
              <ListEditor
                name="progress"
                label="进展记录"
                value={draft.progress}
                change={(value) => update("progress", value)}
                error={errors.progress}
              />
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
  startAdding = false,
}: {
  original: NonNullable<Snapshot["product"]>;
  snapshot: Snapshot;
  close: () => void;
  saved: () => Promise<void>;
  reload: () => void;
  startAdding?: boolean;
}) {
  const [draft, setDraft] = useState<Product>(structuredClone(original.data));
  const isStringList = (value: unknown): value is string[] =>
    Array.isArray(value) && value.every((item) => typeof item === "string");
  const initialJson = Object.fromEntries(
    Object.entries(original.data)
      .filter(([, value]) => typeof value !== "string" && !isStringList(value))
      .map(([key, value]) => [key, JSON.stringify(value, null, 2)]),
  );
  const [jsonDrafts, setJsonDrafts] =
    useState<Record<string, string>>(initialJson);
  const [adding, setAdding] = useState(startAdding);
  const [newName, setNewName] = useState("");
  const [nameError, setNameError] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const canLeave = useLeaveGuard(
    JSON.stringify(draft) !== JSON.stringify(original.data) ||
      JSON.stringify(jsonDrafts) !== JSON.stringify(initialJson) ||
      !!newName,
  );
  const changed = snapshot.product?.version !== original.version;
  const update = <K extends keyof Product>(name: K, value: Product[K]) =>
    setDraft({ ...draft, [name]: value });
  const addField = () => {
    const name = newName.trim();
    if (!name) {
      setNameError("请填写字段名称");
      return;
    }
    if (Object.hasOwn(draft, name)) {
      setNameError("该字段已经存在");
      return;
    }
    if (["__proto__", "constructor", "prototype"].includes(name)) {
      setNameError("不能使用系统保留名称");
      return;
    }
    setDraft({ ...draft, [name]: "" });
    setNewName("");
    setNameError("");
    setAdding(false);
    requestAnimationFrame(() =>
      document
        .getElementById(`product-field-${Object.keys(draft).length}`)
        ?.focus(),
    );
  };
  const submit = async () => {
    if (adding && newName.trim()) {
      setNameError("请先将字段添加到表单，或取消新增");
      return;
    }
    const candidate = { ...draft };
    const jsonErrors: Errors = {};
    for (const [key, value] of Object.entries(jsonDrafts)) {
      try {
        candidate[key] = JSON.parse(value);
      } catch {
        jsonErrors[key] = "请输入有效的 JSON 内容";
      }
    }
    if (Object.keys(jsonErrors).length) {
      setErrors(jsonErrors);
      return;
    }
    const checked = productSchema.safeParse(candidate);
    if (!checked.success) {
      setErrors(errorsFor(checked.error));
      return;
    }
    setPending(true);
    setError("");
    setErrors({});
    try {
      await api("/product", "PUT", {
        data: checked.data,
        version: original.version,
      });
      await saved();
      toast.add({ title: "产品信息已保存", type: "success" });
      close();
    } catch (error) {
      setError((error as Error).message);
      await saved();
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
          <DialogTitle>编辑产品信息</DialogTitle>
          <DialogDescription>
            这些信息是长期产品依据。仅在产品定位或约束明确变化时修改。
          </DialogDescription>
        </DialogHeader>
        <form
          id="product-form"
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
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
              {adding ? (
                <FieldSet>
                  <FieldLegend variant="label">增加字段</FieldLegend>
                  <FieldGroup>
                    <TextField
                      name="new-product-field"
                      label="字段名称"
                      value={newName}
                      change={setNewName}
                      error={nameError}
                    />
                    <div className="flex gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        onClick={addField}
                      >
                        <PlusIcon data-icon="inline-start" />
                        添加到表单
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        onClick={() => {
                          setAdding(false);
                          setNewName("");
                          setNameError("");
                        }}
                      >
                        取消新增
                      </Button>
                    </div>
                  </FieldGroup>
                </FieldSet>
              ) : (
                <Button
                  type="button"
                  variant="outline"
                  className="self-start"
                  onClick={() => {
                    setAdding(true);
                    requestAnimationFrame(() =>
                      document.getElementById("new-product-field")?.focus(),
                    );
                  }}
                >
                  <PlusIcon data-icon="inline-start" />
                  增加字段
                </Button>
              )}
              {Object.entries(draft).map(([key, value], index) => {
                const label = productFieldLabel(key);
                const name = `product-field-${index}`;
                if (Object.hasOwn(jsonDrafts, key))
                  return (
                    <TextField
                      key={key}
                      name={name}
                      label={label}
                      value={jsonDrafts[key]}
                      change={(text) =>
                        setJsonDrafts({ ...jsonDrafts, [key]: text })
                      }
                      error={errors[key]}
                      multiline
                      description="以 JSON 编辑，保存时保留数字、布尔值、对象或数组类型。"
                    />
                  );
                if (isStringList(value))
                  return (
                    <ListEditor
                      key={key}
                      name={name}
                      label={label}
                      value={value}
                      change={(items) => update(key, items)}
                      error={errors[key]}
                    />
                  );
                return (
                  <TextField
                    key={key}
                    name={name}
                    label={label}
                    value={String(value)}
                    change={(text) => update(key, text)}
                    error={errors[key]}
                    multiline={key !== "users"}
                  />
                );
              })}
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
          <Button
            type="submit"
            form="product-form"
            disabled={pending || changed}
          >
            <SaveIcon data-icon="inline-start" />
            {pending ? "正在保存…" : "保存产品信息"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
