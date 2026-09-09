import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

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
export function MarkdownContent({
  value,
  empty = "暂无内容",
}: {
  value: string;
  empty?: string;
}) {
  return (
    <div className="document-markdown">
      {value.trim() ? (
        <Markdown
          remarkPlugins={[remarkGfm]}
          skipHtml
          components={{
            a: ({ node, ...props }) => (
              <a {...props} target="_blank" rel="noopener noreferrer" />
            ),
            table: ({ node, ...props }) => (
              <div className="max-w-full overflow-x-auto">
                <table {...props} />
              </div>
            ),
          }}
        >
          {value}
        </Markdown>
      ) : (
        <p className="text-muted-foreground">{empty}</p>
      )}
    </div>
  );
}
export function MarkdownTitle({ value }: { value: string }) {
  return (
    <Markdown
      skipHtml
      allowedElements={["strong", "em", "code", "del"]}
      unwrapDisallowed
    >
      {value}
    </Markdown>
  );
}
export function ProductFields({
  product,
}: {
  product: Record<string, string>;
}) {
  return (
    <>
      {Object.entries(product).map(([key, value]) => (
        <section
          key={key}
          className="flex min-w-0 flex-col gap-3"
          aria-label={productFieldLabel(key)}
        >
          <h2 className="break-words">{productFieldLabel(key)}</h2>
          <MarkdownContent value={value} />
        </section>
      ))}
    </>
  );
}
