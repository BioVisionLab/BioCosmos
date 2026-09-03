import { setWorkerUrl } from "maplibre-gl";

// Served from public/maplibre by scripts/copy_maplibre_worker.mjs, which the
// dev and build scripts run. MapLibre's own worker URL resolves to a path
// Turbopack does not emit, so it has to be pointed at the copy explicitly.
const WORKER_URL = "/maplibre/maplibre-gl-worker.mjs";

let configured = false;

export function configureMapLibreWorker(): void {
  if (configured) {
    return;
  }

  setWorkerUrl(WORKER_URL);
  configured = true;
}
