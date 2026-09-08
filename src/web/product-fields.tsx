import type { Product } from "../shared/protocol";

const labels: Record<string, string> = {
  summary: "产品描述",
  users: "主要用户",
  coreRequirements: "核心需求",
  constraints: "长期约束",
  nonGoals: "明确不做",
};

export function productFieldLabel(key: string) {
  return Object.hasOwn(labels, key) ? labels[key] : key;
}

function ProductValue({
  value,
  depth = 0,
}: {
  value: unknown;
  depth?: number;
}) {
  if (value === null)
    return <p className="text-sm text-muted-foreground">未设置</p>;
  if (typeof value === "boolean")
    return <p className="text-sm">{value ? "是" : "否"}</p>;
  if (typeof value !== "object")
    return (
      <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">
        {String(value) || "（空文本）"}
      </p>
    );
  if (depth >= 8)
    return (
      <pre className="whitespace-pre-wrap break-all text-sm">
        {JSON.stringify(value, null, 2)}
      </pre>
    );
  if (Array.isArray(value)) {
    if (!value.length)
      return <p className="text-sm text-muted-foreground">暂无条目</p>;
    return (
      <ol className="flex flex-col gap-3">
        {value.map((item, index) => (
          <li className="flex min-w-0 items-start gap-3" key={index}>
            <span
              className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded bg-muted text-xs text-muted-foreground"
              aria-hidden="true"
            >
              {index + 1}
            </span>
            <div className="min-w-0 flex-1">
              <ProductValue value={item} depth={depth + 1} />
            </div>
          </li>
        ))}
      </ol>
    );
  }
  const entries = Object.entries(value);
  if (!entries.length)
    return <p className="text-sm text-muted-foreground">暂无字段</p>;
  return (
    <dl className="flex min-w-0 flex-col gap-4">
      {entries.map(([key, item]) => (
        <div key={key} className="flex min-w-0 flex-col gap-1">
          <dt className="break-words text-sm font-medium text-muted-foreground">
            {key}
          </dt>
          <dd className="min-w-0">
            <ProductValue value={item} depth={depth + 1} />
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function ProductFields({ product }: { product: Product }) {
  return (
    <>
      {Object.entries(product).map(([key, value]) => (
        <section
          key={key}
          className="flex min-w-0 flex-col gap-3"
          aria-label={productFieldLabel(key)}
        >
          <h2 className="break-words">{productFieldLabel(key)}</h2>
          <ProductValue value={value} />
        </section>
      ))}
    </>
  );
}
