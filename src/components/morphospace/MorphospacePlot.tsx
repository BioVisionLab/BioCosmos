"use client";

import "./morphospace.css";
import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import { useRouter } from "next/navigation";

import NoImage from "@/components/NoImage";
import { imageUrlById } from "@/lib/images";
import type { AxisExtreme, ScopeMorphospace, Side } from "@/lib/morphospace";
import { speciesPageHref } from "@/lib/taxonSlug";

type AxisKey = "pc1" | "pc2" | "pc3";
type View = "both" | Side;

const AXIS_PAIRS: [AxisKey, AxisKey][] = [
  ["pc1", "pc2"],
  ["pc1", "pc3"],
  ["pc2", "pc3"],
];
const AXIS_INDEX: Record<AxisKey, number> = { pc1: 0, pc2: 1, pc3: 2 };

// Above this many visible points, every dorsal–ventral link would be noise;
// links are then drawn only for the selected species.
const LINK_LIMIT = 400;
const HIT_RADIUS = 10;
const PADDING = { top: 12, right: 16, bottom: 40, left: 52 };
/** How many genera or species can be compared at once, one color each. */
export const MAX_SELECTION = 5;
// How many filter matches the picker lists before asking for a narrower filter.
const OPTION_LIMIT = 60;
// One thumbnail size for the species at both ends of both axes.
const AXIS_IMAGE = 40;

const SHAPES = [
  "circle",
  "square",
  "triangle",
  "diamond",
  "triangleDown",
] as const;
type Shape = (typeof SHAPES)[number];

/** Keyboard focus ring, visible on both surfaces (WCAG 2.4.7). */
export const FOCUS_RING =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-deep-mocha-800 dark:focus-visible:outline-deep-mocha-100";
/** Secondary text: at least 4.5:1 on the card and page surfaces. */
export const MUTED_TEXT = "text-deep-mocha-600 dark:text-deep-mocha-400";

export interface MorphospaceSelection {
  kind: "genus" | "species";
  /** Lower-case genus key, or the accepted species name. */
  key: string;
  label: string;
}

interface Selected extends MorphospaceSelection {
  slot: number;
}

interface Palette {
  dorsal: string;
  ventral: string;
  series: string[];
  muted: string;
  link: string;
  surface: string;
  grid: string;
  axis: string;
}

interface Props {
  data: ScopeMorphospace;
  /** Selected when the plot mounts, e.g. the species whose page this is. */
  initialSelection?: MorphospaceSelection[];
  height?: number;
}

function readPalette(element: HTMLElement): Palette {
  const style = getComputedStyle(element);
  const token = (name: string) => style.getPropertyValue(`--ms-${name}`).trim();
  // The ring around each point has to match whatever the plot sits on.
  let surface = "";
  for (
    let node: HTMLElement | null = element;
    node;
    node = node.parentElement
  ) {
    const background = getComputedStyle(node).backgroundColor;
    if (
      background &&
      background !== "rgba(0, 0, 0, 0)" &&
      background !== "transparent"
    ) {
      surface = background;
      break;
    }
  }
  return {
    dorsal: token("dorsal"),
    ventral: token("ventral"),
    series: SHAPES.map((_, slot) => token(`series-${slot + 1}`)),
    muted: token("muted"),
    link: token("link"),
    surface: surface || token("surface"),
    grid: token("grid"),
    axis: token("axis"),
  };
}

function tracePath(
  ctx: CanvasRenderingContext2D,
  shape: Shape,
  x: number,
  y: number,
  r: number,
) {
  ctx.beginPath();
  switch (shape) {
    case "circle":
      ctx.arc(x, y, r, 0, Math.PI * 2);
      break;
    case "square":
      ctx.rect(x - r * 0.9, y - r * 0.9, r * 1.8, r * 1.8);
      break;
    case "triangle":
      ctx.moveTo(x, y - r * 1.2);
      ctx.lineTo(x + r * 1.1, y + r * 0.8);
      ctx.lineTo(x - r * 1.1, y + r * 0.8);
      ctx.closePath();
      break;
    case "triangleDown":
      ctx.moveTo(x, y + r * 1.2);
      ctx.lineTo(x + r * 1.1, y - r * 0.8);
      ctx.lineTo(x - r * 1.1, y - r * 0.8);
      ctx.closePath();
      break;
    case "diamond":
      ctx.moveTo(x, y - r * 1.25);
      ctx.lineTo(x + r * 1.25, y);
      ctx.lineTo(x, y + r * 1.25);
      ctx.lineTo(x - r * 1.25, y);
      ctx.closePath();
      break;
  }
}

/** One mark with a surface-colored ring; filled for dorsal, hollow for ventral. */
function drawMark(
  ctx: CanvasRenderingContext2D,
  shape: Shape,
  x: number,
  y: number,
  r: number,
  color: string,
  filled: boolean,
  surface: string,
) {
  tracePath(ctx, shape, x, y, r + 1.5);
  ctx.fillStyle = surface;
  ctx.fill();
  if (filled) {
    tracePath(ctx, shape, x, y, r);
    ctx.fillStyle = color;
    ctx.fill();
  } else {
    tracePath(ctx, shape, x, y, r - 1);
    ctx.lineWidth = 2;
    ctx.strokeStyle = color;
    ctx.stroke();
  }
}

/** The same marks as SVG, for the legend and the selection chips. */
export function ShapeIcon({
  shape = "circle",
  color,
  filled = true,
  size = 12,
}: {
  shape?: Shape;
  color: string;
  filled?: boolean;
  size?: number;
}) {
  const c = size / 2;
  const r = size / 2 - 2;
  const paint = filled
    ? { fill: color }
    : { fill: "none", stroke: color, strokeWidth: 2 };
  const polygon = (pts: [number, number][]) => (
    <polygon
      points={pts.map(([x, y]) => `${c + x * r},${c + y * r}`).join(" ")}
      {...paint}
    />
  );
  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      aria-hidden
      className="shrink-0"
    >
      {shape === "circle" && (
        <circle cx={c} cy={c} r={filled ? r : r - 0.5} {...paint} />
      )}
      {shape === "square" && (
        <rect
          x={c - r * 0.9}
          y={c - r * 0.9}
          width={r * 1.8}
          height={r * 1.8}
          {...paint}
        />
      )}
      {shape === "triangle" &&
        polygon([
          [0, -1.1],
          [1, 0.8],
          [-1, 0.8],
        ])}
      {shape === "triangleDown" &&
        polygon([
          [0, 1.1],
          [1, -0.8],
          [-1, -0.8],
        ])}
      {shape === "diamond" &&
        polygon([
          [0, -1.1],
          [1.1, 0],
          [0, 1.1],
          [-1.1, 0],
        ])}
    </svg>
  );
}

/**
 * The 1-SD ellipse of one species-side's photographs. Stored for PC1 × PC2
 * only. Traced in data space and mapped point by point, which is exact because
 * the axis scales are linear.
 */
function strokeEllipse(
  ctx: CanvasRenderingContext2D,
  points: ScopeMorphospace["points"],
  i: number,
  sx: (v: number) => number,
  sy: (v: number) => number,
  color: string,
) {
  const cx = points.ellX[i],
    cy = points.ellY[i];
  const a = points.ellSx[i],
    b = points.ellSy[i];
  const rho = points.ellRho[i] ?? 0;
  if (cx == null || cy == null || a == null || b == null) return;
  // Principal axes of the 2 × 2 covariance.
  const cxx = a * a,
    cyy = b * b,
    cxy = rho * a * b;
  const mid = (cxx + cyy) / 2;
  const diff = Math.sqrt(((cxx - cyy) / 2) ** 2 + cxy * cxy);
  const l1 = Math.sqrt(Math.max(mid + diff, 0));
  const l2 = Math.sqrt(Math.max(mid - diff, 0));
  const angle = 0.5 * Math.atan2(2 * cxy, cxx - cyy);
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.globalAlpha = 0.8;
  ctx.beginPath();
  for (let step = 0; step <= 48; step++) {
    const t = (step / 48) * Math.PI * 2;
    const ex = l1 * Math.cos(t),
      ey = l2 * Math.sin(t);
    const x = sx(cx + ex * Math.cos(angle) - ey * Math.sin(angle));
    const y = sy(cy + ex * Math.sin(angle) + ey * Math.cos(angle));
    if (step === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();
  ctx.globalAlpha = 1;
}

function clipToPlot(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
) {
  ctx.beginPath();
  ctx.rect(
    PADDING.left,
    PADDING.top,
    width - PADDING.left - PADDING.right,
    height - PADDING.top - PADDING.bottom,
  );
  ctx.clip();
}

function niceTicks(min: number, max: number, count = 5): number[] {
  const span = max - min;
  if (!(span > 0)) return [min];
  const raw = span / count;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const step =
    [1, 2, 2.5, 5, 10]
      .map((m) => m * magnitude)
      .find((s) => span / s <= count) ?? 10 * magnitude;
  const ticks: number[] = [];
  for (let t = Math.ceil(min / step) * step; t <= max + 1e-9; t += step) {
    ticks.push(Number(t.toFixed(6)));
  }
  return ticks;
}

function formatName(value: string | null | undefined) {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : "";
}

export default function MorphospacePlot({
  data,
  initialSelection = [],
  height = 440,
}: Props) {
  const router = useRouter();
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const gridRef = useRef<Map<string, number[]>>(new Map());
  const screenRef = useRef<Float32Array>(new Float32Array(0));
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const scaleRef = useRef<{
    sx: (v: number) => number;
    sy: (v: number) => number;
    palette: Palette;
  } | null>(null);

  const [width, setWidth] = useState(0);
  const [view, setView] = useState<View>("both");
  const [axes, setAxes] = useState<[AxisKey, AxisKey]>(["pc1", "pc2"]);
  const [selected, setSelected] = useState<Selected[]>(() =>
    initialSelection.slice(0, MAX_SELECTION).map((s, slot) => ({ ...s, slot })),
  );
  const [onlySelected, setOnlySelected] = useState(false);
  // The hovered point and where it was drawn, captured at hover time so
  // render never reads the canvas refs.
  const [hover, setHover] = useState<{
    i: number;
    x: number;
    y: number;
  } | null>(null);
  const hovered = hover?.i ?? null;
  const [themeTick, setThemeTick] = useState(0);
  const [colors, setcolors] = useState<string[]>([]);

  const { points, scope, extremes } = data;
  const count = points.species.length;

  // Genera and species a reader can pick from. Inside a genus only species
  // make sense; elsewhere both.
  const options = useMemo(() => {
    const genera = new Map<string, Set<string>>();
    const species = new Map<string, string | null>();
    for (let i = 0; i < count; i++) {
      const g = points.genus[i];
      if (g) {
        if (!genera.has(g)) genera.set(g, new Set());
        genera.get(g)!.add(points.species[i]);
      }
      species.set(points.species[i], g);
    }
    const out: (MorphospaceSelection & { detail: string })[] = [];
    if (scope.rank !== "genus") {
      for (const [g, members] of [...genera].sort((a, b) =>
        a[0].localeCompare(b[0]),
      )) {
        out.push({
          kind: "genus",
          key: g,
          label: formatName(g),
          detail: `genus · ${members.size} spp.`,
        });
      }
    }
    for (const name of [...species.keys()].sort()) {
      out.push({ kind: "species", key: name, label: name, detail: "species" });
    }
    return out;
  }, [count, points, scope.rank]);

  // The selection slot each point belongs to, or -1. A selected species wins
  // over a selected genus containing it.
  const slotOf = useMemo(() => {
    const slots = new Int8Array(count).fill(-1);
    if (selected.length === 0) return slots;
    const bySpecies = new Map(
      selected.filter((s) => s.kind === "species").map((s) => [s.key, s.slot]),
    );
    const byGenus = new Map(
      selected.filter((s) => s.kind === "genus").map((s) => [s.key, s.slot]),
    );
    for (let i = 0; i < count; i++) {
      const slot =
        bySpecies.get(points.species[i]) ?? byGenus.get(points.genus[i] ?? "");
      if (slot !== undefined) slots[i] = slot;
    }
    return slots;
  }, [count, points, selected]);

  const hasSelection = selected.length > 0;

  const visible = useMemo(() => {
    const out: number[] = [];
    for (let i = 0; i < count; i++) {
      if (view !== "both" && points.side[i] !== view) continue;
      if (onlySelected && hasSelection && slotOf[i] < 0) continue;
      out.push(i);
    }
    return out;
  }, [count, points.side, view, onlySelected, hasSelection, slotOf]);

  // Both sides of each species, for the hover card's two photographs.
  const sidesOf = useMemo(() => {
    const map = new Map<string, Partial<Record<Side, number>>>();
    for (let i = 0; i < count; i++) {
      const entry = map.get(points.species[i]) ?? {};
      entry[points.side[i]] = i;
      map.set(points.species[i], entry);
    }
    return map;
  }, [count, points]);

  // Width tracking and theme changes both trigger a redraw.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const resize = new ResizeObserver(([entry]) =>
      setWidth(Math.floor(entry.contentRect.width)),
    );
    resize.observe(container);
    const theme = new MutationObserver(() => setThemeTick((t) => t + 1));
    theme.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });
    return () => {
      resize.disconnect();
      theme.disconnect();
    };
  }, []);

  const [xKey, yKey] = axes;
  const xs = points[xKey];
  const ys = points[yKey];

  const bounds = useMemo(() => {
    let minX = Infinity,
      maxX = -Infinity,
      minY = Infinity,
      maxY = -Infinity;
    for (let i = 0; i < count; i++) {
      minX = Math.min(minX, xs[i]);
      maxX = Math.max(maxX, xs[i]);
      minY = Math.min(minY, ys[i]);
      maxY = Math.max(maxY, ys[i]);
    }
    const padX = (maxX - minX || 1) * 0.05;
    const padY = (maxY - minY || 1) * 0.05;
    return {
      minX: minX - padX,
      maxX: maxX + padX,
      minY: minY - padY,
      maxY: maxY + padY,
    };
  }, [count, xs, ys]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container || width === 0) return;
    const palette = readPalette(container);
    const ratio = window.devicePixelRatio || 1;
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);

    const plotW = width - PADDING.left - PADDING.right;
    const plotH = height - PADDING.top - PADDING.bottom;
    const sx = (v: number) =>
      PADDING.left + ((v - bounds.minX) / (bounds.maxX - bounds.minX)) * plotW;
    const sy = (v: number) =>
      PADDING.top +
      (1 - (v - bounds.minY) / (bounds.maxY - bounds.minY)) * plotH;

    // Recessive grid; tick and axis labels in the text color.
    ctx.font = "11px ui-sans-serif, system-ui, sans-serif";
    ctx.lineWidth = 1;
    ctx.strokeStyle = palette.grid;
    ctx.fillStyle = palette.axis;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    for (const t of niceTicks(bounds.minX, bounds.maxX)) {
      const x = Math.round(sx(t)) + 0.5;
      ctx.beginPath();
      ctx.moveTo(x, PADDING.top);
      ctx.lineTo(x, PADDING.top + plotH);
      ctx.stroke();
      ctx.fillText(String(t), x, PADDING.top + plotH + 7);
    }
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    for (const t of niceTicks(bounds.minY, bounds.maxY)) {
      const y = Math.round(sy(t)) + 0.5;
      ctx.beginPath();
      ctx.moveTo(PADDING.left, y);
      ctx.lineTo(PADDING.left + plotW, y);
      ctx.stroke();
      ctx.fillText(String(t), PADDING.left - 8, y);
    }
    // Axis lines on the plot's left and bottom edges, with outward ticks. The
    // bottom edge is the x axis: its ticks, values and title sit below it, and
    // the low-end thumbnail of the y axis ends exactly on it.
    const left = PADDING.left + 0.5;
    const bottom = PADDING.top + plotH + 0.5;
    ctx.strokeStyle = palette.axis;
    ctx.beginPath();
    ctx.moveTo(left, PADDING.top);
    ctx.lineTo(left, bottom);
    ctx.lineTo(PADDING.left + plotW, bottom);
    for (const t of niceTicks(bounds.minX, bounds.maxX)) {
      const x = Math.round(sx(t)) + 0.5;
      ctx.moveTo(x, bottom);
      ctx.lineTo(x, bottom + 4);
    }
    for (const t of niceTicks(bounds.minY, bounds.maxY)) {
      const y = Math.round(sy(t)) + 0.5;
      ctx.moveTo(left - 4, y);
      ctx.lineTo(left, y);
    }
    ctx.stroke();

    const label = (key: AxisKey) =>
      `${key.toUpperCase()} (${(scope.explained[AXIS_INDEX[key]] * 100).toFixed(1)}%)`;
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";
    ctx.fillText(label(xKey), PADDING.left + plotW / 2, height - 2);
    ctx.save();
    ctx.translate(12, PADDING.top + plotH / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textBaseline = "middle";
    ctx.fillText(label(yKey), 0, 0);
    ctx.restore();

    const dense = visible.length > 2000;
    const radius = dense ? 3 : 4;
    const screen = new Float32Array(count * 2).fill(NaN);
    for (const i of visible) {
      screen[i * 2] = sx(xs[i]);
      screen[i * 2 + 1] = sy(ys[i]);
    }
    screenRef.current = screen;
    scaleRef.current = { sx, sy, palette };

    const color = (i: number) =>
      slotOf[i] >= 0
        ? palette.series[slotOf[i]]
        : points.side[i] === "dorsal"
          ? palette.dorsal
          : palette.ventral;

    // Dorsal–ventral links: consecutive entries of one species, sorted
    // species-then-side by the backend.
    if (view === "both") {
      ctx.lineWidth = 1;
      const allLinks = visible.length <= LINK_LIMIT;
      for (let i = 0; i + 1 < count; i++) {
        if (points.species[i] !== points.species[i + 1]) continue;
        if (Number.isNaN(screen[i * 2]) || Number.isNaN(screen[(i + 1) * 2]))
          continue;
        const inSelection = slotOf[i] >= 0;
        if (!allLinks && !inSelection) continue;
        ctx.strokeStyle = inSelection
          ? palette.series[slotOf[i]]
          : palette.link;
        ctx.globalAlpha = inSelection ? 0.9 : hasSelection ? 0.35 : 0.7;
        ctx.beginPath();
        ctx.moveTo(screen[i * 2], screen[i * 2 + 1]);
        ctx.lineTo(screen[(i + 1) * 2], screen[(i + 1) * 2 + 1]);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }

    // Intraspecific spread, for selected species only: every species' ellipse
    // at once buries the points it is meant to explain.
    if (
      xKey === "pc1" &&
      yKey === "pc2" &&
      selected.some((s) => s.kind === "species")
    ) {
      const speciesSlots = new Set(
        selected.filter((s) => s.kind === "species").map((s) => s.key),
      );
      ctx.save();
      clipToPlot(ctx, width, height);
      for (const i of visible) {
        if (speciesSlots.has(points.species[i])) {
          strokeEllipse(ctx, points, i, sx, sy, color(i));
        }
      }
      ctx.restore();
    }

    // Points: context first, selection on top.
    for (const i of visible) {
      if (slotOf[i] >= 0) continue;
      ctx.globalAlpha = hasSelection ? 1 : dense ? 0.6 : 0.9;
      drawMark(
        ctx,
        "circle",
        screen[i * 2],
        screen[i * 2 + 1],
        radius,
        hasSelection ? palette.muted : color(i),
        points.side[i] === "dorsal",
        palette.surface,
      );
    }
    ctx.globalAlpha = 1;
    for (const i of visible) {
      if (slotOf[i] < 0) continue;
      drawMark(
        ctx,
        SHAPES[slotOf[i]],
        screen[i * 2],
        screen[i * 2 + 1],
        radius + 1.5,
        color(i),
        points.side[i] === "dorsal",
        palette.surface,
      );
    }

    // Hit-testing grid over the drawn points.
    const grid = new Map<string, number[]>();
    for (const i of visible) {
      const key = `${Math.floor(screen[i * 2] / HIT_RADIUS)},${Math.floor(screen[i * 2 + 1] / HIT_RADIUS)}`;
      const cell = grid.get(key);
      if (cell) cell.push(i);
      else grid.set(key, [i]);
    }
    gridRef.current = grid;
    setcolors((previous) =>
      previous.join() === palette.series.join() ? previous : palette.series,
    );
    // `themeTick` is read so a theme change re-runs this callback.
    void themeTick;
  }, [
    width,
    height,
    bounds,
    visible,
    xs,
    ys,
    xKey,
    yKey,
    points,
    scope,
    slotOf,
    selected,
    hasSelection,
    view,
    count,
    themeTick,
  ]);

  useEffect(() => {
    draw();
  }, [draw]);

  // The hovered species, both sides, on a canvas of its own so hovering
  // never redraws thousands of points.
  useEffect(() => {
    const overlay = overlayRef.current;
    const scale = scaleRef.current;
    if (!overlay || !scale || width === 0) return;
    const ratio = window.devicePixelRatio || 1;
    overlay.width = width * ratio;
    overlay.height = height * ratio;
    overlay.style.width = `${width}px`;
    overlay.style.height = `${height}px`;
    const ctx = overlay.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);
    if (hovered == null) return;
    const { sx, sy, palette } = scale;
    const name = points.species[hovered];
    const members = visible.filter((i) => points.species[i] === name);
    const color = (i: number) =>
      slotOf[i] >= 0
        ? palette.series[slotOf[i]]
        : points.side[i] === "dorsal"
          ? palette.dorsal
          : palette.ventral;
    if (xKey === "pc1" && yKey === "pc2") {
      ctx.save();
      clipToPlot(ctx, width, height);
      for (const i of members) strokeEllipse(ctx, points, i, sx, sy, color(i));
      ctx.restore();
    }
    if (members.length === 2) {
      ctx.strokeStyle = palette.axis;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(sx(xs[members[0]]), sy(ys[members[0]]));
      ctx.lineTo(sx(xs[members[1]]), sy(ys[members[1]]));
      ctx.stroke();
    }
    for (const i of members) {
      ctx.beginPath();
      ctx.arc(sx(xs[i]), sy(ys[i]), 8, 0, Math.PI * 2);
      ctx.lineWidth = 2;
      ctx.strokeStyle = palette.axis;
      ctx.stroke();
    }
  }, [
    hovered,
    width,
    height,
    points,
    visible,
    xs,
    ys,
    xKey,
    yKey,
    slotOf,
    themeTick,
  ]);

  const pick = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const cx = Math.floor(x / HIT_RADIUS);
    const cy = Math.floor(y / HIT_RADIUS);
    const screen = screenRef.current;
    let best: number | null = null;
    let bestDistance = HIT_RADIUS * HIT_RADIUS;
    for (let dx = -1; dx <= 1; dx++) {
      for (let dy = -1; dy <= 1; dy++) {
        for (const i of gridRef.current.get(`${cx + dx},${cy + dy}`) ?? []) {
          const d = (screen[i * 2] - x) ** 2 + (screen[i * 2 + 1] - y) ** 2;
          // Prefer selected points when two overlap.
          const bias = slotOf[i] >= 0 ? 0.5 : 1;
          if (d * bias < bestDistance) {
            bestDistance = d * bias;
            best = i;
          }
        }
      }
    }
    return best == null
      ? null
      : { i: best, x: screen[best * 2], y: screen[best * 2 + 1] };
  };

  const toggle = (option: MorphospaceSelection) => {
    setSelected((current) => {
      const existing = current.find(
        (s) => s.kind === option.kind && s.key === option.key,
      );
      if (existing) return current.filter((s) => s !== existing);
      if (current.length >= MAX_SELECTION) return current;
      // The lowest free slot, so a color follows its entity and removing one
      // selection never repaints the others.
      const used = new Set(current.map((s) => s.slot));
      const slot = SHAPES.findIndex((_, n) => !used.has(n));
      return [...current, { ...option, slot }];
    });
  };

  const hoveredHref =
    hovered != null ? speciesPageHref(points.pageKey[hovered]) : null;
  const tooltipStyle = (() => {
    if (hover == null) return undefined;
    const { x, y } = hover;
    const left = x > width - 260 ? x - 252 : x + 14;
    return {
      left: Math.max(0, left),
      top: Math.max(0, Math.min(y - 60, height - 200)),
    };
  })();

  const extremeFor = (axis: AxisKey, end: "min" | "max") =>
    extremes.find((e) => e.axis === axis && e.end === end);

  const tableRows = (
    hasSelection ? visible.filter((i) => slotOf[i] >= 0) : visible
  ).slice(0, 300);

  return (
    <div className="morphospace-viz">
      <div className="flex flex-wrap items-center gap-2 mb-3 text-sm">
        <Segmented
          label="Side"
          value={view}
          options={[
            ["both", "Both"],
            ["dorsal", "Dorsal"],
            ["ventral", "Ventral"],
          ]}
          onChange={(v) => setView(v as View)}
        />
        <Segmented
          label="Axes"
          value={axes.join("-")}
          options={AXIS_PAIRS.filter(
            ([, y]) => scope.explained[AXIS_INDEX[y]] > 0,
          ).map(([x, y]) => [
            `${x}-${y}`,
            `${x.toUpperCase()} × ${y.toUpperCase()}`,
          ])}
          onChange={(v) => setAxes(v.split("-") as [AxisKey, AxisKey])}
        />
        <SelectionPicker
          options={options}
          selected={selected}
          onToggle={toggle}
        />
      </div>

      <SelectionBar
        selected={selected}
        colors={colors}
        onlySelected={onlySelected}
        onOnlySelected={setOnlySelected}
        onRemove={toggle}
        onClear={() => setSelected([])}
      />

      <Legend
        selection={hasSelection}
        onlySelected={onlySelected}
        linked={view === "both"}
        ellipse={xKey === "pc1" && yKey === "pc2"}
      />

      <div className="flex w-full">
        <YAxisEnds
          axis={yKey}
          low={extremeFor(yKey, "min")}
          high={extremeFor(yKey, "max")}
          height={height}
        />
        <div
          ref={containerRef}
          className="relative min-w-0 flex-1"
          style={{ height }}
        >
          <canvas
            ref={canvasRef}
            role="img"
            aria-label={`Morphospace of ${scope.name}: ${visible.length} species-side points on ${xKey.toUpperCase()} and ${yKey.toUpperCase()}. The same points are listed in the data table below.`}
            className={hoveredHref ? "cursor-pointer" : "cursor-crosshair"}
            onMouseMove={(e) => setHover(pick(e))}
            onMouseLeave={() => setHover(null)}
            onClick={(e) => {
              const hit = pick(e);
              const href = hit ? speciesPageHref(points.pageKey[hit.i]) : null;
              if (href) router.push(href);
            }}
          />
          <canvas
            ref={overlayRef}
            aria-hidden
            className="pointer-events-none absolute inset-0"
          />
          {hovered != null && (
            <HoverCard
              points={points}
              index={hovered}
              sides={sidesOf.get(points.species[hovered]) ?? {}}
              xKey={xKey}
              yKey={yKey}
              linked={Boolean(hoveredHref)}
              style={tooltipStyle}
            />
          )}
        </div>
      </div>

      <XAxisEnds
        axis={xKey}
        low={extremeFor(xKey, "min")}
        high={extremeFor(xKey, "max")}
      />

      <details className="mt-3 text-sm">
        <summary
          className={`cursor-pointer rounded ${MUTED_TEXT} ${FOCUS_RING}`}
        >
          Data table{hasSelection ? " (selection)" : ""}
        </summary>
        <DataTable
          data={data}
          xKey={xKey}
          yKey={yKey}
          rows={tableRows}
          total={
            hasSelection
              ? visible.filter((i) => slotOf[i] >= 0).length
              : visible.length
          }
        />
      </details>
    </div>
  );
}

function Segmented({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: [string, string][];
  onChange: (value: string) => void;
}) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="inline-flex rounded-md border border-deep-mocha-300 dark:border-deep-mocha-600"
    >
      {options.map(([key, text]) => (
        <button
          key={key}
          type="button"
          role="radio"
          aria-checked={value === key}
          onClick={() => onChange(key)}
          className={`min-h-7 px-2.5 py-1 first:rounded-l-md last:rounded-r-md ${FOCUS_RING} ${
            value === key
              ? "bg-deep-mocha-700 text-white dark:bg-deep-mocha-200 dark:text-deep-mocha-950 font-medium"
              : "hover:bg-deep-mocha-100 dark:hover:bg-deep-mocha-800"
          }`}
        >
          {text}
        </button>
      ))}
    </div>
  );
}

/** A filterable, keyboard-operable checklist of genera and species, capped at five. */
function SelectionPicker({
  options,
  selected,
  onToggle,
}: {
  options: (MorphospaceSelection & { detail: string })[];
  selected: Selected[];
  onToggle: (option: MorphospaceSelection) => void;
}) {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const id = useId();
  const full = selected.length >= MAX_SELECTION;

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (
        !panelRef.current?.contains(event.target as Node) &&
        event.target !== buttonRef.current
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const isSelected = (o: MorphospaceSelection) =>
    selected.some((s) => s.kind === o.kind && s.key === o.key);
  const needle = filter.trim().toLowerCase();
  const matches = options.filter(
    (o) => !needle || o.label.toLowerCase().includes(needle),
  );
  const shown = matches.slice(0, OPTION_LIMIT);
  const noun = options.some((o) => o.kind === "genus")
    ? "genera or species"
    : "species";

  return (
    <div className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-expanded={open}
        aria-controls={`${id}-panel`}
        onClick={() => setOpen((o) => !o)}
        className={`min-h-7 rounded-md border border-deep-mocha-300 dark:border-deep-mocha-600 px-2.5 py-1 hover:bg-deep-mocha-100 dark:hover:bg-deep-mocha-800 ${FOCUS_RING}`}
      >
        Compare {noun} ({selected.length}/{MAX_SELECTION}) ▾
      </button>
      {open && (
        <div
          ref={panelRef}
          id={`${id}-panel`}
          role="group"
          aria-label={`Choose up to ${MAX_SELECTION} ${noun}`}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              setOpen(false);
              buttonRef.current?.focus();
            }
          }}
          className="absolute left-0 z-20 mt-1 w-72 max-w-[calc(100vw-2rem)] rounded-lg border border-deep-mocha-300 dark:border-deep-mocha-600 bg-white dark:bg-deep-mocha-950 p-2 shadow-lg"
        >
          <label
            htmlFor={`${id}-filter`}
            className="block text-xs font-medium mb-1"
          >
            Filter
          </label>
          <input
            id={`${id}-filter`}
            type="search"
            autoFocus
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder={`Type to filter ${noun}`}
            className={`w-full rounded-md border border-deep-mocha-400 dark:border-deep-mocha-500 bg-transparent px-2 py-1 text-sm placeholder:text-deep-mocha-600 dark:placeholder:text-deep-mocha-400 ${FOCUS_RING}`}
          />
          <p
            role="status"
            aria-live="polite"
            className={`mt-1 text-xs ${MUTED_TEXT}`}
          >
            {selected.length} of {MAX_SELECTION} selected
            {full ? " — remove one to add another" : ""}
          </p>
          <ul className="mt-1 max-h-60 overflow-auto">
            {shown.map((option) => {
              const checked = isSelected(option);
              const disabled = full && !checked;
              return (
                <li key={`${option.kind}:${option.key}`}>
                  <label
                    className={`flex min-h-7 items-center gap-2 rounded px-1 py-0.5 text-sm ${
                      disabled
                        ? "opacity-60 cursor-not-allowed"
                        : "cursor-pointer hover:bg-deep-mocha-100 dark:hover:bg-deep-mocha-800"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={disabled}
                      onChange={() => onToggle(option)}
                      className={FOCUS_RING}
                    />
                    <span className="italic truncate">{option.label}</span>
                    <span className={`ml-auto shrink-0 text-xs ${MUTED_TEXT}`}>
                      {option.detail}
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
          {matches.length > shown.length && (
            <p className={`mt-1 text-xs ${MUTED_TEXT}`}>
              Showing {shown.length} of {matches.length} · type to narrow the
              list
            </p>
          )}
          {matches.length === 0 && (
            <p className={`mt-1 text-xs ${MUTED_TEXT}`}>No matches.</p>
          )}
        </div>
      )}
    </div>
  );
}

/** The current selection as removable chips; also the legend for its colors and shapes. */
function SelectionBar({
  selected,
  colors,
  onlySelected,
  onOnlySelected,
  onRemove,
  onClear,
}: {
  selected: Selected[];
  colors: string[];
  onlySelected: boolean;
  onOnlySelected: (value: boolean) => void;
  onRemove: (option: MorphospaceSelection) => void;
  onClear: () => void;
}) {
  if (selected.length === 0) return null;
  return (
    <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
      <ul aria-label="Selected" className="flex flex-wrap gap-1.5">
        {[...selected]
          .sort((a, b) => a.slot - b.slot)
          .map((s) => (
            <li
              key={`${s.kind}:${s.key}`}
              className="inline-flex items-center gap-1.5 rounded-full border border-deep-mocha-300 dark:border-deep-mocha-600 pl-2 pr-0.5 py-0.5"
            >
              <ShapeIcon
                shape={SHAPES[s.slot]}
                color={colors[s.slot] ?? "currentColor"}
                size={14}
              />
              <span className="italic">{s.label}</span>
              <span className={`text-xs ${MUTED_TEXT}`}>{s.kind}</span>
              <button
                type="button"
                aria-label={`Remove ${s.label}`}
                onClick={() => onRemove(s)}
                className={`grid h-6 w-6 place-items-center rounded-full hover:bg-deep-mocha-100 dark:hover:bg-deep-mocha-800 ${FOCUS_RING}`}
              >
                ×
              </button>
            </li>
          ))}
      </ul>
      <label className="inline-flex min-h-7 items-center gap-1.5 cursor-pointer">
        <input
          type="checkbox"
          checked={onlySelected}
          onChange={(e) => onOnlySelected(e.target.checked)}
          className={FOCUS_RING}
        />
        Show only selected
      </label>
      <button
        type="button"
        onClick={onClear}
        className={`min-h-7 rounded-md px-2 underline ${FOCUS_RING}`}
      >
        Clear
      </button>
    </div>
  );
}

function Legend({
  selection,
  onlySelected,
  linked,
  ellipse,
}: {
  selection: boolean;
  onlySelected: boolean;
  linked: boolean;
  ellipse: boolean;
}) {
  const item = "inline-flex items-center gap-1.5";
  return (
    <ul className={`flex flex-wrap gap-x-4 gap-y-1 mb-2 text-xs ${MUTED_TEXT}`}>
      {selection ? (
        <>
          <li className={item}>
            <ShapeIcon color="var(--ms-axis)" />
            Filled: dorsal
          </li>
          <li className={item}>
            <ShapeIcon color="var(--ms-axis)" filled={false} />
            Hollow: ventral
          </li>
          {!onlySelected && (
            <li className={item}>
              <ShapeIcon color="var(--ms-muted)" />
              Other species
            </li>
          )}
        </>
      ) : (
        <>
          <li className={item}>
            <ShapeIcon color="var(--ms-dorsal)" />
            Dorsal
          </li>
          <li className={item}>
            <ShapeIcon color="var(--ms-ventral)" filled={false} />
            Ventral
          </li>
        </>
      )}
      {linked && (
        <li className={item}>
          <span
            className="inline-block w-4 h-px"
            style={{ background: "var(--ms-link)" }}
          />
          Joins a species&apos; dorsal and ventral centroids
        </li>
      )}
      {ellipse && (
        <li className={item}>
          <span
            className="inline-block w-4 h-2.5 rounded-full border"
            style={{ borderColor: "var(--ms-link)" }}
          />
          Spread of a species&apos; photographs (1 SD), for selected or hovered
          species
        </li>
      )}
    </ul>
  );
}

/** A representative photograph with a fixed frame, and a labelled placeholder if it fails. */
function RepresentativeImage({
  imgId,
  alt,
  size,
}: {
  imgId: string | null | undefined;
  alt: string;
  size: number;
}) {
  const [failed, setFailed] = useState(false);
  const frame =
    "shrink-0 rounded-md border border-deep-mocha-200 dark:border-deep-mocha-700 bg-deep-mocha-50 dark:bg-deep-mocha-900";
  if (!imgId || failed) {
    return (
      <span
        className={`${frame} relative block`}
        style={{ width: size, height: size }}
      >
        <NoImage className="text-center text-[10px] leading-tight [&>svg]:h-4 [&>svg]:w-4" />
      </span>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={imageUrlById(imgId, "thumbnail")}
      alt={alt}
      loading="lazy"
      onError={() => setFailed(true)}
      className={`${frame} object-contain`}
      style={{ width: size, height: size }}
    />
  );
}

function HoverCard({
  points,
  index,
  sides,
  xKey,
  yKey,
  linked,
  style,
}: {
  points: ScopeMorphospace["points"];
  index: number;
  sides: Partial<Record<Side, number>>;
  xKey: AxisKey;
  yKey: AxisKey;
  linked: boolean;
  style?: React.CSSProperties;
}) {
  const name = points.species[index];
  return (
    <div
      className="pointer-events-none absolute z-10 w-60 rounded-lg border border-deep-mocha-300 dark:border-deep-mocha-600 bg-white dark:bg-deep-mocha-950 p-2.5 shadow-lg text-xs"
      style={style}
    >
      <p className="font-semibold italic text-sm">{name}</p>
      <div className="mt-2 grid grid-cols-2 gap-2">
        {(["dorsal", "ventral"] as const).map((side) => {
          const i = sides[side];
          return (
            <figure
              key={side}
              className={side === points.side[index] ? "" : "opacity-80"}
            >
              <RepresentativeImage
                imgId={i != null ? points.imgId[i] : null}
                alt={`${name}, representative ${side} photograph`}
                size={104}
              />
              <figcaption className="mt-0.5">
                <span
                  className={side === points.side[index] ? "font-semibold" : ""}
                >
                  {side === "dorsal" ? "Dorsal" : "Ventral"}
                </span>{" "}
                <span className={MUTED_TEXT}>
                  {i != null
                    ? `${points.nImages[i].toLocaleString()} img`
                    : "none"}
                </span>
              </figcaption>
            </figure>
          );
        })}
      </div>
      <p className={`mt-1.5 tabular-nums ${MUTED_TEXT}`}>
        {points.side[index] === "dorsal" ? "Dorsal" : "Ventral"} point:{" "}
        {xKey.toUpperCase()} {points[xKey][index].toFixed(3)} ·{" "}
        {yKey.toUpperCase()} {points[yKey][index].toFixed(3)}
      </p>
      {linked && (
        <p className={`mt-0.5 ${MUTED_TEXT}`}>
          Click the point to open the species page
        </p>
      )}
    </div>
  );
}

function extremeLink(
  e: AxisExtreme,
  children: React.ReactNode,
  className: string,
) {
  const href = speciesPageHref(e.pageKey);
  return href ? (
    <a
      href={href}
      className={`${className} hover:underline rounded ${FOCUS_RING}`}
    >
      {children}
    </a>
  ) : (
    <span className={className}>{children}</span>
  );
}

/**
 * The species at each end of the y axis, set along the axis. Text runs bottom
 * to top like the axis title: which end, then the species. Each end owns half
 * the plot height and its text uses all of it, wrapping rather than truncating.
 */
function YAxisEnds({
  axis,
  low,
  high,
  height,
}: {
  axis: AxisKey;
  low?: AxisExtreme;
  high?: AxisExtreme;
  height: number;
}) {
  if (!low || !high) return null;
  const vertical = {
    writingMode: "vertical-rl" as const,
    transform: "rotate(180deg)",
  };
  const IMAGE = AXIS_IMAGE;
  const GAP = 4;
  // Half the plot height each, less the thumbnail and a gap between the ends.
  const half = (height - PADDING.top - PADDING.bottom) / 2;
  const textLength = Math.max(48, half - IMAGE - GAP * 3);
  const end = (label: string, e: AxisExtreme, place: "top" | "bottom") => {
    const text = (
      <span
        // Rotated 180°, a vertical line starts at the bottom; the top end's
        // text aligns to its end so it sits against its thumbnail.
        style={{
          ...vertical,
          maxHeight: textLength,
          textAlign: place === "top" ? "end" : "start",
        }}
        className="text-[11px] leading-tight wrap-break-words"
        title={`${label}: ${e.species} (${e.side})`}
      >
        <span className="block font-medium">{label}</span>
        <span className="block italic">
          {e.species}{" "}
          <span className={`not-italic ${MUTED_TEXT}`}>({e.side})</span>
        </span>
      </span>
    );
    const image = (
      <RepresentativeImage
        imgId={e.imgId}
        alt={`${e.species}, ${e.side}`}
        size={IMAGE}
      />
    );
    return extremeLink(
      e,
      place === "top" ? (
        <>
          {image}
          {text}
        </>
      ) : (
        <>
          {text}
          {image}
        </>
      ),
      `flex flex-col items-center gap-1 ${place === "top" ? "justify-start" : "justify-end"}`,
    );
  };
  return (
    <div
      className="grid w-12 shrink-0 justify-items-center"
      style={{
        height,
        paddingTop: PADDING.top,
        paddingBottom: PADDING.bottom,
        gridTemplateRows: "1fr 1fr",
        rowGap: GAP * 2,
      }}
    >
      {end(`High ${axis.toUpperCase()}`, high, "top")}
      {end(`Low ${axis.toUpperCase()}`, low, "bottom")}
    </div>
  );
}

function XAxisEnds({
  axis,
  low,
  high,
}: {
  axis: AxisKey;
  low?: AxisExtreme;
  high?: AxisExtreme;
}) {
  if (!low || !high) return null;
  const end = (label: string, e: AxisExtreme, align: string) =>
    extremeLink(
      e,
      <>
        <RepresentativeImage
          imgId={e.imgId}
          alt={`${e.species}, ${e.side}`}
          size={AXIS_IMAGE}
        />
        <span className={`text-xs ${align}`}>
          <span className="block font-medium">{label}</span>
          <span className="italic">{e.species}</span>{" "}
          <span className={MUTED_TEXT}>({e.side})</span>
        </span>
      </>,
      `flex items-center gap-2 ${align === "text-right" ? "flex-row-reverse" : ""}`,
    );
  return (
    <div className="mt-2 ml-12 flex flex-wrap items-center justify-between gap-2">
      {end(`Low ${axis.toUpperCase()}`, low, "text-left")}
      {end(`High ${axis.toUpperCase()}`, high, "text-right")}
    </div>
  );
}

function DataTable({
  data,
  xKey,
  yKey,
  rows,
  total,
}: {
  data: ScopeMorphospace;
  xKey: AxisKey;
  yKey: AxisKey;
  rows: number[];
  total: number;
}) {
  const { points } = data;
  return (
    <div
      className="mt-2 max-h-72 overflow-auto"
      tabIndex={0}
      aria-label="Morphospace data table"
    >
      <table className="w-full text-xs tabular-nums">
        <caption className="sr-only">
          Species centroids on {xKey.toUpperCase()} and {yKey.toUpperCase()}
        </caption>
        <thead className="sticky top-0 bg-white dark:bg-deep-mocha-950">
          <tr className={`text-left ${MUTED_TEXT}`}>
            <th scope="col" className="py-1 pr-2 font-medium">
              Species
            </th>
            <th scope="col" className="py-1 pr-2 font-medium">
              Side
            </th>
            <th scope="col" className="py-1 pr-2 font-medium text-right">
              {xKey.toUpperCase()}
            </th>
            <th scope="col" className="py-1 pr-2 font-medium text-right">
              {yKey.toUpperCase()}
            </th>
            <th scope="col" className="py-1 font-medium text-right">
              Images
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((i) => (
            <tr
              key={i}
              className="border-t border-deep-mocha-100 dark:border-deep-mocha-800"
            >
              <td className="py-1 pr-2 italic">{points.species[i]}</td>
              <td className="py-1 pr-2">
                {points.side[i] === "dorsal" ? "Dorsal" : "Ventral"}
              </td>
              <td className="py-1 pr-2 text-right">
                {points[xKey][i].toFixed(3)}
              </td>
              <td className="py-1 pr-2 text-right">
                {points[yKey][i].toFixed(3)}
              </td>
              <td className="py-1 text-right">
                {points.nImages[i].toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length < total && (
        <p className={`mt-1 ${MUTED_TEXT}`}>
          Showing {rows.length} of {total} points.
        </p>
      )}
    </div>
  );
}
