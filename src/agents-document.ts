import { AppError } from "./shared/protocol";

export const USER_START = "<!-- repoframe:user:start -->";
export const USER_END = "<!-- repoframe:user:end -->";
export function userRegion(source: string) {
  const start = source.indexOf(USER_START),
    end = source.indexOf(USER_END);
  if (
    start < 0 ||
    end < start ||
    source.indexOf(USER_START, start + USER_START.length) >= 0 ||
    source.indexOf(USER_END, end + USER_END.length) >= 0
  )
    throw new AppError(
      "AGENTS.md 用户区域缺失或标记无效，请运行 init 整理入口",
      409,
    );
  return { start: start + USER_START.length, end };
}
export function agentsUserContent(source: string) {
  const { start, end } = userRegion(source);
  return source
    .slice(start, end)
    .replace(/^\r?\n/, "")
    .replace(/\r?\n$/, "");
}
export function replaceAgentsUserContent(source: string, content: string) {
  if (/<!--\s*repoframe:/i.test(content))
    throw new AppError("用户内容不能包含 RepoFrame 区域标记", 422);
  const { start, end } = userRegion(source);
  return source.slice(0, start) + "\n" + content + "\n" + source.slice(end);
}
export function directDocuments(source: string) {
  // Direct repository paths in inline code, Markdown links or prose are routes.
  return new Set(
    Array.from(
      source
        .replaceAll("\\", "/")
        .matchAll(/\.agents\/docs\/([^\s`<>"\[\]()]+\.md)\b/gi),
      (m) => m[1].toLowerCase(),
    ),
  );
}
export function organizeAgents(source: string | null, template: string) {
  if (source === null) return template;
  if (source.includes(USER_START) || source.includes(USER_END)) {
    userRegion(source);
    return source;
  }
  const managed = source.match(
    /<!-- repoframe:start -->([\s\S]*?)<!-- repoframe:end -->/,
  );
  if (!managed && /<!--\s*repoframe:(?:start|end)\s*-->/.test(source))
    throw new AppError("AGENTS.md 固定区域标记不完整，请修正后重试", 409);
  const user = (managed ? source.replace(managed[0], "") : source).trim();
  let result = replaceAgentsUserContent(template, user);
  if (managed && managed[1].includes("## RepoFrame 开发入口")) {
    const known = directDocuments(template);
    const extra = managed[1]
      .split(/\r?\n/)
      .filter((line) =>
        [...directDocuments(line)].some((file) => !known.has(file)),
      );
    if (extra.length)
      result = result.replace(
        "<!-- repoframe:end -->",
        `## 补充固定路由\n\n${extra.join("\n")}\n\n<!-- repoframe:end -->`,
      );
  }
  // Preserve custom rules in legacy managed blocks rather than discarding them.
  if (managed && !managed[1].includes("## RepoFrame 开发入口"))
    result = result.replace(
      "<!-- repoframe:end -->",
      `### 原有固定规则\n${managed[1].trim()}\n\n<!-- repoframe:end -->`,
    );
  return result;
}
