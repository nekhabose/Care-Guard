import { cn } from "../../lib/cn";

// Deterministic, calm color per patient so the same person keeps the same hue.
const PALETTE = [
  "bg-brand-100 text-brand-800 dark:bg-brand-500/15 dark:text-brand-200",
  "bg-sky-100 text-sky-800 dark:bg-sky-500/15 dark:text-sky-200",
  "bg-violet-100 text-violet-800 dark:bg-violet-500/15 dark:text-violet-200",
  "bg-rose-100 text-rose-800 dark:bg-rose-500/15 dark:text-rose-200",
  "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-200",
  "bg-indigo-100 text-indigo-800 dark:bg-indigo-500/15 dark:text-indigo-200",
];

function hash(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h;
}

export function Avatar({
  initials,
  seed,
  size = "md",
}: {
  initials: string;
  seed: string;
  size?: "sm" | "md" | "lg";
}) {
  const color = PALETTE[hash(seed) % PALETTE.length];
  const sizing =
    size === "lg"
      ? "h-12 w-12 text-base"
      : size === "sm"
        ? "h-8 w-8 text-xs"
        : "h-10 w-10 text-sm";
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full font-bold",
        sizing,
        color,
      )}
    >
      {initials}
    </span>
  );
}
