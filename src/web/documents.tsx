import { useEffect, useRef, useState } from "react";
import {
  FileTextIcon,
  FolderPlusIcon,
  PencilIcon,
  PlusIcon,
  SaveIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardAction,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Field,
  FieldGroup,
  FieldLabel,
  FieldError,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  NativeSelect,
  NativeSelectOption,
} from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/toast";
import { api } from "./api";
import { MarkdownContent } from "./product-fields";
import { useLeaveGuard } from "./editors";
import {
  documentSchema,
  emptyIndex,
  type DocumentsSnapshot,
  type DocumentFile,
  type DocumentEntry,
} from "../shared/documents";

type Editor = {
  original: DocumentFile;
  entry?: DocumentEntry;
  root: boolean;
  fresh: boolean;
  indexVersion: string | null;
};

export function DocumentsView({
  revision,
  disabled,
}: {
  revision: unknown;
  disabled: boolean;
}) {
  const [data, setData] = useState<DocumentsSnapshot | null>(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState("@agents");
  const [editor, setEditor] = useState<Editor | null>(null);
  const [category, setCategory] = useState<{
    id?: string;
    name: string;
    version: string | null;
  } | null>(null);
  const sequence = useRef(0);
  const refresh = async () => {
    const request = ++sequence.current;
    try {
      const next = await api<DocumentsSnapshot>("/documents");
      if (sequence.current === request) {
        setData(next);
        setError("");
      }
    } catch (error) {
      if (sequence.current === request) setError((error as Error).message);
    }
  };
  useEffect(() => {
    void refresh();
    return () => {
      sequence.current++;
    };
  }, [revision]);
  if (!data)
    return error ? (
      <Alert variant="destructive">
        <AlertTitle>{error}</AlertTitle>
        <Button onClick={() => void refresh()}>重试</Button>
      </Alert>
    ) : (
      <Skeleton className="h-72 w-full" />
    );
  const index = data.index?.data ?? emptyIndex();
  const root = selected === "@agents";
  const current = root
    ? data.agents
    : data.files.find((f) => f.file === selected);
  const metadata = index.documents.find((d) => d.file === selected);
  const indexInvalid = data.diagnostics.some(
    (d) => d.file === ".agents/docs/index.json",
  );
  const edit = () =>
    current &&
    setEditor({
      original: current,
      entry: metadata,
      root,
      fresh: false,
      indexVersion: data.index?.version ?? null,
    });
  const groups = [
    ...index.categories.map((c) => ({
      ...c,
      files: data.files.filter((f) =>
        index.documents.some((d) => d.file === f.file && d.category === c.id),
      ),
    })),
    {
      id: "@uncategorized",
      name: "未分类",
      files: data.files.filter((f) =>
        index.documents.some((d) => d.file === f.file && d.category === null),
      ),
    },
    {
      id: "@unregistered",
      name: "待补充说明",
      files: data.files.filter(
        (f) => !index.documents.some((d) => d.file === f.file),
      ),
    },
  ];
  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1>文档</h1>
        <div className="flex gap-2">
          <Button
            variant="outline"
            disabled={disabled || indexInvalid}
            onClick={() =>
              setCategory({ name: "", version: data.index?.version ?? null })
            }
          >
            <FolderPlusIcon data-icon="inline-start" />
            新增类别
          </Button>
          <Button
            disabled={disabled || indexInvalid}
            onClick={() =>
              setEditor({
                original: { file: "", content: "", version: null },
                root: false,
                fresh: true,
                indexVersion: data.index?.version ?? null,
              })
            }
          >
            <PlusIcon data-icon="inline-start" />
            新增文件
          </Button>
        </div>
      </div>
      {error && (
        <Alert variant="destructive">
          <AlertTitle>{error}</AlertTitle>
          <Button variant="link" onClick={() => void refresh()}>
            重试
          </Button>
        </Alert>
      )}
      {data.diagnostics.map((d) => (
        <Alert key={d.file} variant="destructive">
          <AlertTitle>{d.message}</AlertTitle>
          <AlertDescription>{d.file}</AlertDescription>
        </Alert>
      ))}
      <div className="grid min-w-0 items-start gap-5 lg:grid-cols-[220px_minmax(0,1fr)]">
        <nav aria-label="文档目录" className="flex min-w-0 flex-col gap-5">
          <Button
            variant={root ? "secondary" : "ghost"}
            className="justify-start"
            aria-current={root ? "page" : undefined}
            onClick={() => setSelected("@agents")}
          >
            <FileTextIcon data-icon="inline-start" />
            AGENTS.md
          </Button>
          {groups
            .filter((g) => !g.id.startsWith("@") || g.files.length > 0)
            .map((group) => (
              <section key={group.id} className="flex min-w-0 flex-col gap-1">
                <div className="flex items-center justify-between gap-2 px-2">
                  <h2 className="truncate text-xs font-medium text-muted-foreground">
                    {group.name}
                  </h2>
                  {!group.id.startsWith("@") && (
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label={`重命名类别 ${group.name}`}
                      disabled={disabled || indexInvalid}
                      onClick={() =>
                        setCategory({
                          id: group.id,
                          name: group.name,
                          version: data.index?.version ?? null,
                        })
                      }
                    >
                      <PencilIcon data-icon="inline-start" />
                    </Button>
                  )}
                </div>
                {group.files.length === 0 && (
                  <p className="px-2 py-2 text-xs text-muted-foreground">
                    暂无文件
                  </p>
                )}
                {group.files.map((file) => (
                  <Button
                    key={file.file}
                    variant={selected === file.file ? "secondary" : "ghost"}
                    className="max-w-full justify-start"
                    aria-current={selected === file.file ? "page" : undefined}
                    onClick={() => setSelected(file.file)}
                    title={file.file}
                  >
                    <FileTextIcon data-icon="inline-start" />
                    <span className="truncate">
                      {index.documents.find((d) => d.file === file.file)
                        ?.name ?? file.file}
                    </span>
                  </Button>
                ))}
              </section>
            ))}
        </nav>
        <Card className="min-w-0 min-h-96">
          <CardHeader>
            <CardTitle>
              {root ? "AGENTS.md" : (metadata?.name ?? selected)}
            </CardTitle>
            <CardDescription className="break-all">
              {root ? "用户约定" : `.agents/docs/${selected}`}
            </CardDescription>
            <CardAction>
              <Button
                variant="ghost"
                size="icon"
                aria-label="编辑文档"
                disabled={
                  disabled ||
                  !current ||
                  (!root && indexInvalid) ||
                  data.diagnostics.some(
                    (d) =>
                      d.file === (root ? "AGENTS.md" : selected) &&
                      d.message !== "索引引用的文件不存在",
                  )
                }
                onClick={edit}
              >
                <PencilIcon data-icon="inline-start" />
              </Button>
            </CardAction>
          </CardHeader>
          <CardContent className="flex min-w-0 flex-col gap-6">
            {!root &&
              (metadata ? (
                <div className="flex flex-col gap-2">
                  <Badge variant="secondary">何时读取</Badge>
                  <p className="text-sm text-muted-foreground">
                    {metadata.description}
                  </p>
                </div>
              ) : (
                <Badge variant="outline">待补充说明</Badge>
              ))}
            <MarkdownContent
              value={current?.content ?? ""}
              empty={
                current?.content === null
                  ? "文件尚不存在，可以通过编辑创建。"
                  : "暂无内容"
              }
            />
          </CardContent>
        </Card>
      </div>
      {editor && (
        <DocumentEditor
          editor={editor}
          data={data}
          disabled={disabled}
          close={() => setEditor(null)}
          refresh={refresh}
          saved={(file) => {
            setSelected(editor.root ? "@agents" : file);
            setEditor(null);
          }}
          reload={() => {
            const latest = editor.root
              ? data.agents
              : data.files.find((f) => f.file === editor.original.file);
            setEditor({
              ...editor,
              original: latest ?? editor.original,
              entry: index.documents.find(
                (d) => d.file === editor.original.file,
              ),
              indexVersion: data.index?.version ?? null,
            });
          }}
          key={`${editor.original.file}:${editor.original.version}:${editor.indexVersion}`}
        />
      )}
      {category && (
        <CategoryEditor
          original={category}
          data={data}
          disabled={disabled}
          close={() => setCategory(null)}
          refresh={refresh}
        />
      )}
    </>
  );
}

function DocumentEditor({
  editor,
  data,
  disabled,
  close,
  refresh,
  saved,
  reload,
}: {
  editor: Editor;
  data: DocumentsSnapshot;
  disabled: boolean;
  close: () => void;
  refresh: () => Promise<void>;
  saved: (file: string) => void;
  reload: () => void;
}) {
  const initial = {
    file: editor.original.file,
    name: editor.entry?.name ?? editor.original.file.replace(/\.md$/, ""),
    category: editor.entry?.category ?? null,
    description: editor.entry?.description ?? "",
    content: editor.original.content ?? "",
  };
  const [draft, setDraft] = useState(initial);
  const [error, setError] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [pending, setPending] = useState(false);
  const leave = useLeaveGuard(
    JSON.stringify(initial) !== JSON.stringify(draft),
  );
  const latest = editor.root
    ? data.agents
    : data.files.find((f) => f.file === draft.file);
  const changed =
    (latest?.version ?? null) !== editor.original.version ||
    (!editor.root && (data.index?.version ?? null) !== editor.indexVersion);
  const update = (key: string, value: string | null) =>
    setDraft({ ...draft, [key]: value });
  const finish = () => {
    if (!pending && leave()) close();
  };
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) finish();
      }}
    >
      <DialogContent
        className="flex max-h-[90dvh] flex-col sm:max-w-3xl"
        showCloseButton={!pending}
      >
        <DialogHeader>
          <DialogTitle>
            {editor.root
              ? "编辑用户约定"
              : editor.fresh
                ? "新增文件"
                : "编辑文档"}
          </DialogTitle>
          <DialogDescription>
            {editor.root
              ? "仅编辑 AGENTS.md 的用户约定区域"
              : "正文保存为 Markdown，何时读取保存到文档索引。"}
          </DialogDescription>
        </DialogHeader>
        <form
          className="flex min-h-0 flex-col gap-5"
          onSubmit={async (event) => {
            event.preventDefault();
            const checked = documentSchema.safeParse(draft);
            if (!editor.root && !checked.success) {
              setErrors(
                Object.fromEntries(
                  checked.error.issues.map((i) => [
                    String(i.path[0]),
                    i.message,
                  ]),
                ),
              );
              return;
            }
            setPending(true);
            setError("");
            setErrors({});
            try {
              await api(
                editor.root ? "/documents/agents" : "/documents/file",
                "PUT",
                {
                  file: draft.file,
                  content: draft.content,
                  version: editor.original.version,
                  metadata: checked.success ? checked.data : undefined,
                  indexVersion: editor.indexVersion,
                },
              );
              await refresh();
              saved(draft.file);
              toast.add({ title: "文档已保存", type: "success" });
            } catch (error) {
              setError((error as Error).message);
              await refresh();
            } finally {
              setPending(false);
            }
          }}
        >
          <div className="flex min-h-0 flex-col gap-5 overflow-y-auto px-1 [scrollbar-gutter:stable]">
            {(changed || error) && (
              <Alert variant={error ? "destructive" : "default"}>
                <AlertTitle>
                  {error || "文件或目录在编辑期间发生变化"}
                </AlertTitle>
                <AlertDescription>
                  当前草稿已保留。
                  <Button
                    type="button"
                    variant="link"
                    disabled={pending}
                    onClick={() => {
                      if (leave()) reload();
                    }}
                  >
                    重新加载
                  </Button>
                </AlertDescription>
              </Alert>
            )}
            <FieldGroup>
              {!editor.root && (
                <>
                  {(
                    [
                      ["name", "名称"],
                      ["file", "文件路径"],
                      ["description", "何时读取"],
                    ] as const
                  ).map(([key, label]) => (
                    <Field key={key} data-invalid={!!errors[key]}>
                      <FieldLabel htmlFor={`doc-${key}`}>{label}</FieldLabel>
                      <Input
                        id={`doc-${key}`}
                        value={draft[key]}
                        disabled={pending || (key === "file" && !editor.fresh)}
                        placeholder={
                          key === "file"
                            ? "testing.md"
                            : key === "description"
                              ? "新增或修改代码、准备验证结果时读取。"
                              : undefined
                        }
                        onChange={(e) => update(key, e.target.value)}
                        aria-invalid={!!errors[key]}
                      />
                      {errors[key] && <FieldError>{errors[key]}</FieldError>}
                    </Field>
                  ))}
                  <Field>
                    <FieldLabel htmlFor="doc-category">类别</FieldLabel>
                    <NativeSelect
                      id="doc-category"
                      value={draft.category ?? ""}
                      disabled={pending}
                      onChange={(e) =>
                        update("category", e.target.value || null)
                      }
                    >
                      <NativeSelectOption value="">未分类</NativeSelectOption>
                      {data.index?.data.categories.map((c) => (
                        <NativeSelectOption key={c.id} value={c.id}>
                          {c.name}
                        </NativeSelectOption>
                      ))}
                    </NativeSelect>
                  </Field>
                </>
              )}
              <Field>
                <FieldLabel htmlFor="doc-content">Markdown 正文</FieldLabel>
                <Textarea
                  id="doc-content"
                  className="min-h-60"
                  value={draft.content}
                  disabled={pending}
                  onChange={(e) => update("content", e.target.value)}
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
            <Button type="submit" disabled={pending || disabled || changed}>
              <SaveIcon data-icon="inline-start" />
              {pending ? "保存中…" : "保存"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function CategoryEditor({
  original,
  data,
  disabled,
  close,
  refresh,
}: {
  original: { name: string; id?: string; version: string | null };
  data: DocumentsSnapshot;
  disabled: boolean;
  close: () => void;
  refresh: () => Promise<void>;
}) {
  const [name, setName] = useState(original.name);
  const [version, setVersion] = useState(original.version);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const leave = useLeaveGuard(name !== original.name);
  const finish = () => {
    if (!pending && leave()) close();
  };
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) finish();
      }}
    >
      <DialogContent showCloseButton={!pending}>
        <DialogHeader>
          <DialogTitle>{original.id ? "重命名类别" : "新增类别"}</DialogTitle>
        </DialogHeader>
        <form
          className="flex flex-col gap-5"
          onSubmit={async (event) => {
            event.preventDefault();
            setPending(true);
            setError("");
            try {
              await api("/documents/categories", "POST", {
                name,
                id: original.id,
                version,
              });
              await refresh();
              close();
            } catch (error) {
              setError((error as Error).message);
              await refresh();
            } finally {
              setPending(false);
            }
          }}
        >
          {error && (
            <Alert variant="destructive">
              <AlertTitle>{error}</AlertTitle>
            </Alert>
          )}
          {(data.index?.version ?? null) !== version && (
            <Alert>
              <AlertTitle>文档目录已变化</AlertTitle>
              <Button
                type="button"
                variant="link"
                onClick={() => {
                  setVersion(data.index?.version ?? null);
                  setError("");
                }}
              >
                加载最新目录并保留输入
              </Button>
            </Alert>
          )}
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="category-name">类别名称</FieldLabel>
              <Input
                id="category-name"
                value={name}
                required
                maxLength={100}
                disabled={pending}
                onChange={(e) => setName(e.target.value)}
              />
            </Field>
          </FieldGroup>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={pending}
              onClick={finish}
            >
              取消
            </Button>
            <Button
              type="submit"
              disabled={
                pending ||
                disabled ||
                !name.trim() ||
                (data.index?.version ?? null) !== version
              }
            >
              保存类别
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
