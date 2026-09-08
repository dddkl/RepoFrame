import { Hono } from "hono";
import { bodyLimit } from "hono/body-limit";
import { streamSSE } from "hono/streaming";
import { serve } from "@hono/node-server";
import { promises as fs } from "node:fs";
import path from "node:path";
import { EventEmitter } from "node:events";
import { watch } from "chokidar";
import { z } from "zod";
import { Store } from "./store";
import { AppError, parse, modeSchema } from "./shared/protocol";

export function createApp(
  store: Store,
  webRoot: string,
  events = new EventEmitter(),
  port?: number,
) {
  const app = new Hono();
  app.use("*", async (c, next) => {
    const request = new URL(c.req.url);
    const host = c.req.header("host") || request.host;
    const allowed = port
      ? [`127.0.0.1:${port}`, `localhost:${port}`]
      : [request.host];
    if (
      !["127.0.0.1", "localhost"].includes(request.hostname) ||
      !allowed.includes(host)
    )
      return c.json({ error: "只允许从本机地址访问" }, 403);
    if (!["GET", "HEAD"].includes(c.req.method)) {
      if (
        c.req.header("origin") !== `http://${host}` ||
        c.req.header("sec-fetch-site") === "cross-site"
      )
        return c.json({ error: "拒绝跨站写入请求" }, 403);
      if (!c.req.header("content-type")?.startsWith("application/json"))
        return c.json({ error: "请使用 JSON 请求" }, 415);
    }
    c.header("X-Content-Type-Options", "nosniff");
    c.header("Referrer-Policy", "no-referrer");
    c.header(
      "Content-Security-Policy",
      "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'",
    );
    c.header("Cache-Control", "no-store");
    await next();
  });
  app.use(
    "/api/*",
    bodyLimit({
      maxSize: 1024 * 1024,
      onError: (c) => c.json({ error: "内容超过 1 MB 限制" }, 413),
    }),
  );
  app.onError((error, c) => {
    if (error instanceof AppError)
      return c.json({ error: error.message }, error.status as 400);
    if (error instanceof SyntaxError)
      return c.json({ error: "请求 JSON 无效" }, 400);
    console.error(error);
    return c.json(
      {
        error:
          "操作未能完成，请检查文件权限并重新加载；已保存的内容以仓库文件为准",
      },
      500,
    );
  });
  app.get("/api/project", async (c) => c.json(await store.snapshot()));
  app.get("/api/goals", async (c) => {
    const data = await store.snapshot();
    return c.json({ goals: data.goals, diagnostics: data.diagnostics });
  });
  app.get("/api/goals/:id", async (c) => {
    const goal = (await store.snapshot()).goals.find(
      (g) => g.id === c.req.param("id"),
    );
    if (!goal) throw new AppError("目标不存在或无法读取", 404);
    return c.json(goal);
  });
  app.put("/api/state/mode", async (c) => {
    const body = parse(
      z.object({ mode: modeSchema, version: z.string() }),
      await c.req.json(),
    );
    await store.setMode(body.mode, body.version);
    events.emit("change");
    return c.json(await store.snapshot());
  });
  app.put("/api/product", async (c) => {
    const body = parse(
      z.object({ data: z.unknown(), version: z.string() }),
      await c.req.json(),
    );
    await store.saveProduct(body.data, body.version);
    events.emit("change");
    return c.json(await store.snapshot());
  });
  app.post("/api/goals", async (c) => {
    const body = parse(
      z.object({
        data: z.unknown(),
        id: z.string().optional(),
        activate: z.boolean().default(false),
        stateVersion: z.string(),
      }),
      await c.req.json(),
    );
    const id = await store.createGoal(
      body.data,
      body.id,
      body.activate,
      body.stateVersion,
    );
    events.emit("change");
    return c.json({ id, snapshot: await store.snapshot() }, 201);
  });
  app.put("/api/goals/:id", async (c) => {
    const body = parse(
      z.object({ data: z.unknown(), version: z.string() }),
      await c.req.json(),
    );
    await store.editGoal(c.req.param("id"), body.data, body.version);
    events.emit("change");
    return c.json(await store.snapshot());
  });
  app.post("/api/goals/:id/:action", async (c) => {
    const action = parse(
      z.enum(["activate", "pause", "complete"]),
      c.req.param("action"),
    );
    const body = parse(
      z.object({ version: z.string().optional(), stateVersion: z.string() }),
      await c.req.json(),
    );
    await store.goalAction(
      c.req.param("id"),
      action,
      body.version,
      body.stateVersion,
    );
    events.emit("change");
    return c.json(await store.snapshot());
  });
  app.get("/api/events", (c) =>
    streamSSE(c, async (stream) => {
      let finish!: () => void;
      const done = new Promise<void>((resolve) => {
        finish = resolve;
      });
      const notify = () => {
        void stream.writeSSE({ event: "change", data: "reload" }).catch(finish);
      };
      const heartbeat = setInterval(() => {
        void stream.writeSSE({ event: "ping", data: "" }).catch(finish);
      }, 15000);
      heartbeat.unref();
      events.on("change", notify);
      stream.onAbort(finish);
      try {
        await stream.writeSSE({ event: "ready", data: "connected" });
        await done;
      } finally {
        clearInterval(heartbeat);
        events.off("change", notify);
      }
    }),
  );
  app.all("/api/*", (c) =>
    c.json({ error: "接口不存在或请求方法不支持" }, 404),
  );
  app.get("*", async (c) => {
    let requested: string;
    try {
      requested = decodeURIComponent(new URL(c.req.url).pathname);
    } catch {
      throw new AppError("路径无效");
    }
    const relative =
      requested === "/" || !path.extname(requested)
        ? "index.html"
        : requested.slice(1);
    const root = path.resolve(webRoot);
    const target = path.resolve(root, relative);
    if (!target.startsWith(root + path.sep))
      throw new AppError("路径无效", 403);
    try {
      const content = await fs.readFile(target);
      const mime: Record<string, string> = {
        ".html": "text/html; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".svg": "image/svg+xml",
        ".woff2": "font/woff2",
      };
      c.header(
        "Content-Type",
        mime[path.extname(target)] || "application/octet-stream",
      );
      return c.body(content);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT")
        return c.text("页面资源不存在，请先构建 RepoFrame。", 404);
      throw error;
    }
  });
  return app;
}

export async function startServer(root: string, webRoot: string, port: number) {
  const store = new Store(root);
  await store.safePath(".agents");
  const events = new EventEmitter();
  events.setMaxListeners(100);
  const app = createApp(store, webRoot, events, port || undefined);
  const server = serve({ fetch: app.fetch, hostname: "127.0.0.1", port });
  await new Promise<void>((resolve, reject) => {
    server.once("listening", resolve);
    server.once("error", reject);
  });
  const watcher = watch(path.join(root, ".agents"), {
    ignoreInitial: true,
    followSymlinks: false,
    depth: 3,
    awaitWriteFinish: { stabilityThreshold: 150, pollInterval: 50 },
  });
  watcher.on("all", (_event, file) => {
    if (file.endsWith(".json") || !path.extname(file)) events.emit("change");
  });
  watcher.on("error", (error) => console.error("文件监听失败：", error));
  const address = server.address();
  const actualPort =
    typeof address === "object" && address ? address.port : port;
  return {
    port: actualPort,
    async close() {
      await watcher.close();
      if ("closeAllConnections" in server) server.closeAllConnections();
      await new Promise<void>((resolve) => server.close(() => resolve()));
    },
  };
}
