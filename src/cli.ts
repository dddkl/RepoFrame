#!/usr/bin/env node
import { parseArgs } from "node:util";
import { promises as fs } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import open from "open";
import { initialize } from "./initialize";
import { startServer } from "./server";

async function main() {
  const { values, positionals } = parseArgs({
    allowPositionals: true,
    options: {
      repo: { type: "string" },
      port: { type: "string" },
      "no-open": { type: "boolean" },
      help: { type: "boolean", short: "h" },
      version: { type: "boolean", short: "v" },
    },
  });
  const packageRoot = fileURLToPath(new URL("../", import.meta.url));
  if (values.version) {
    const pkg = JSON.parse(
      await fs.readFile(path.join(packageRoot, "package.json"), "utf8"),
    );
    console.log(pkg.version);
    return;
  }
  if (values.help) {
    console.log(
      "RepoFrame · 本地 AI 开发控制面\n\n用法：\n  repoframe init      准备目录与初始化 Skill\n  repoframe           启动中文工作台\n\n选项：\n  --repo <目录>       指定仓库，默认为当前目录\n  --port <端口>       指定本机端口，默认 7331\n  --no-open           不自动打开浏览器\n  -h, --help          显示帮助\n  -v, --version       显示版本\n\n两种开发模式常驻；复杂任务目标仅按需启用。",
    );
    return;
  }
  if (positionals.length > 1 || (positionals[0] && positionals[0] !== "init"))
    throw new Error("未知命令，请运行 repoframe --help");
  const root = path.resolve(values.repo || process.cwd());
  if (!(await fs.stat(root)).isDirectory())
    throw new Error("仓库路径必须是目录");
  if (positionals[0] === "init") {
    const result = await initialize(root, path.join(packageRoot, "templates"));
    console.log(
      `仓库：${root}\n${result.changed.length ? `已准备：\n${result.changed.join("\n")}` : "初始化文件已存在，保留原内容。"}`,
    );
    console.log(
      result.hasPrd
        ? "\n请将以下指令交给现有 Coding Agent：\n读取 .agents/skills/repoframe-init/SKILL.md，从 PRD.md 提炼产品信息，向我展示并确认后写入。"
        : "\n缺少 PRD.md，请先提供需求材料，再让 Coding Agent 按 .agents/skills/repoframe-init/SKILL.md 初始化。",
    );
    console.log("\n运行 repoframe 打开工作台。初始化不会自动创建目标。");
    return;
  }
  const port = Number(values.port || "7331");
  if (!Number.isInteger(port) || port < 1 || port > 65535)
    throw new Error("端口必须是 1 到 65535 之间的整数");
  const server = await startServer(
    root,
    path.join(packageRoot, "dist/web"),
    port,
  );
  const url = `http://127.0.0.1:${server.port}`;
  console.log(
    `RepoFrame 已启动\n仓库：${root}\n工作台：${url}\n按 Ctrl+C 停止。`,
  );
  let stopping = false;
  const close = () => {
    if (stopping) return;
    stopping = true;
    void server.close().then(() => process.exit(0));
  };
  process.on("SIGINT", close);
  process.on("SIGTERM", close);
  if (!values["no-open"])
    await open(url).catch(() =>
      console.log(`浏览器未能自动打开，请访问 ${url}`),
    );
}

main().catch((error) => {
  const code = (error as NodeJS.ErrnoException).code;
  console.error(
    code?.startsWith("ERR_PARSE_ARGS")
      ? "命令参数无效，请运行 repoframe --help 查看用法。"
      : code === "EADDRINUSE"
        ? "端口已被占用，请使用 --port 指定其他端口。"
        : code === "ENOENT"
          ? "目录或必需资源不存在，请检查 --repo 路径并确认安装完整。"
          : `操作失败：${error.message}`,
  );
  process.exitCode = 1;
});
