import { afterEach, beforeEach, expect, it } from "vitest";
import { promises as fs } from "node:fs";
import path from "node:path";
import { Store } from "../src/store";
import { createApp, startServer } from "../src/server";
import { initialize } from "../src/initialize";

let root: string;
let app: ReturnType<typeof createApp>;
const request = (
  route: string,
  method = "GET",
  body?: unknown,
  headers: Record<string, string> = {},
) =>
  app.request(`http://127.0.0.1:7331${route}`, {
    method,
    headers: {
      Host: "127.0.0.1:7331",
      Origin: "http://127.0.0.1:7331",
      "Content-Type": "application/json",
      ...headers,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
beforeEach(async () => {
  const base = path.resolve(".tmp/api");
  await fs.mkdir(base, { recursive: true });
  root = await fs.mkdtemp(path.join(base, "repo-"));
  await initialize(root, path.resolve("templates"));
  app = createApp(new Store(root), path.resolve("dist/web"), undefined, 7331);
});
afterEach(async () => {
  await fs.rm(root, { recursive: true, force: true });
});

it("API 完整执行创建、启用、阻止迭代、暂停和完成", async () => {
  let snapshot = await (await request("/api/project")).json();
  const goal = {
    title: "复杂目标",
    objective: "实现流程",
    doneWhen: "- 验证通过",
    constraints: "",
    progress: { current: null, nodes: [] },
  };
  const created = await request("/api/goals", "POST", {
    data: goal,
    id: "flow",
    activate: true,
    stateVersion: snapshot.state.version,
  });
  expect(created.status).toBe(201);
  snapshot = (await created.json()).snapshot;
  expect(
    (
      await request("/api/state/mode", "PUT", {
        mode: "iteration",
        version: snapshot.state.version,
      })
    ).status,
  ).toBe(409);
  let response = await request("/api/goals/flow/pause", "POST", {
    stateVersion: snapshot.state.version,
  });
  expect(response.status).toBe(200);
  snapshot = await response.json();
  response = await request("/api/goals/flow/complete", "POST", {
    stateVersion: snapshot.state.version,
    version: snapshot.goals[0].version,
  });
  expect((await response.json()).goals[0].data.status).toBe("completed");
});
it("拒绝跨站请求、错误 Host、不支持的方法和格式", async () => {
  expect(
    (
      await request(
        "/api/product",
        "PUT",
        {},
        { Origin: "https://untrusted.example" },
      )
    ).status,
  ).toBe(403);
  expect(
    (
      await request("/api/project", "GET", undefined, {
        Host: "untrusted.example:7331",
      })
    ).status,
  ).toBe(403);
  expect(
    (await request("/api/product", "PUT", {}, { "Content-Type": "text/plain" }))
      .status,
  ).toBe(415);
  expect((await request("/api/project", "DELETE", {})).status).toBe(404);
  expect(
    (await request("/api/state/mode", "PUT", { mode: "other" })).status,
  ).toBe(422);
});
it("真实监听器将外部 JSON 修改通知到 SSE", async () => {
  const running = await startServer(root, path.resolve("dist/web"), 0);
  const abort = new AbortController();
  try {
    const response = await fetch(
      `http://127.0.0.1:${running.port}/api/events`,
      { signal: abort.signal },
    );
    const reader = response.body!.getReader();
    const first = await reader.read();
    expect(new TextDecoder().decode(first.value)).toContain("ready");
    await new Promise((resolve) => setTimeout(resolve, 350));
    await fs.writeFile(
      path.join(root, ".agents/state.json"),
      JSON.stringify({ mode: "iteration", activeGoal: null }),
    );
    const timer = setTimeout(() => abort.abort(), 6000);
    try {
      expect(new TextDecoder().decode((await reader.read()).value)).toContain(
        "change",
      );
    } finally {
      clearTimeout(timer);
      await reader.cancel();
    }
  } finally {
    abort.abort();
    await running.close();
  }
});
