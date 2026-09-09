import type { Progress } from "../../src/shared/progress";
export const graph: Progress = {
  current: 3,
  nodes: [
    {
      id: 0,
      kind: "start",
      title: "开始",
      previous: [],
      status: "done",
      message: "已确定计划。",
    },
    { id: 1, title: "旧方案", previous: [0], status: "abandoned", message: "" },
    {
      id: 2,
      title: "后端实现",
      previous: [0],
      status: "done",
      message: "接口实现通过验证。",
    },
    { id: 3, title: "界面实现", previous: [0], status: "active", message: "" },
    {
      id: 4,
      title: "联合验证",
      previous: [2, 3],
      status: "planned",
      message: "",
    },
    {
      id: 5,
      kind: "end",
      title: "完成",
      previous: [4],
      status: "planned",
      message: "",
    },
  ],
};
