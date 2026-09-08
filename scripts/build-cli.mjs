import { build } from "esbuild";
await build({
  entryPoints: ["src/cli.ts"],
  outfile: "dist/cli.js",
  bundle: true,
  packages: "external",
  platform: "node",
  format: "esm",
  target: "node24",
});
