import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypeScript from "eslint-config-next/typescript";

/**
 * Flat config, run through the ESLint CLI (`bun run lint`).
 *
 * `next lint` was removed in Next 16, so the shareable configs are imported
 * directly rather than pulled in through `FlatCompat`. Both already ignore
 * `.next/`, `out/`, `build/` and `next-env.d.ts`.
 *
 * `next lint` also only ever looked at a fixed set of app directories. The CLI
 * lints the whole repository instead, which is what picks up the root config
 * files — and what makes the ignores below necessary.
 */
const eslintConfig = [
  {
    ignores: [
      // Python virtualenvs vendor bundled JavaScript of their own (pyright
      // ships a 3 MB bundle), and linting it buries every real finding.
      "**/.venv/**",
      // Copied out of maplibre-gl by scripts/copy_maplibre_worker.mjs.
      "public/maplibre/**",
      // Generated harmonization run artifacts; see reports/README.md.
      "reports/*/**",
    ],
  },
  ...nextCoreWebVitals,
  ...nextTypeScript,
];

export default eslintConfig;
