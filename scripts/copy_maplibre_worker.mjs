#!/usr/bin/env node
/**
 * MapLibre resolves its web worker with `new URL('./maplibre-gl-worker.mjs',
 * import.meta.url)`. That path is computed at runtime, so Turbopack cannot
 * rewrite it and the worker 404s from /_next/static/chunks/.
 *
 * Copy the worker and the shared runtime it imports into public/maplibre/ so
 * they sit next to each other on a stable URL. `configureMapLibreWorker()` in
 * src/lib/maplibreWorker.ts points MapLibre at the copy.
 */
import { copyFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";

const WORKER_FILES = ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"];

const require = createRequire(import.meta.url);
const distDir = dirname(require.resolve("maplibre-gl/dist/maplibre-gl.mjs"));
const outDir = join(process.cwd(), "public", "maplibre");

mkdirSync(outDir, { recursive: true });
for (const file of WORKER_FILES) {
  copyFileSync(join(distDir, file), join(outDir, file));
}

console.log(`Copied MapLibre worker assets to ${outDir}`);
