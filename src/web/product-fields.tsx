import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

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
