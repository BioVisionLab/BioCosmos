import type { LucideIcon } from "lucide-react";

/**
 * The `Info` container at full width, with the icon passed in, for the
 * secondary panels under a data tab (notes, links, citations). Each kind gets
 * its own icon so they are told apart at a glance.
 */
function Callout({
  icon: Icon,
  label,
  children,
}: {
  icon: LucideIcon;
  /** Accessible name for the panel. */
  label: string;
  children: React.ReactNode;
}) {
  return (
    <aside
      aria-label={label}
      className="flex mb-2 items-center gap-1 border-l-8 border border-deep-mocha-600/40 bg-deep-mocha-100/10 dark:bg-deep-mocha-800/20 rounded-lg p-2 w-full"
    >
      <div className="flex-shrink-0">
        <Icon className="h-4 w-4 stroke-deep-mocha-500" aria-hidden="true" />
      </div>
      <div className="min-w-0 flex-1 space-y-1 text-xs text-deep-mocha-500">
        {children}
      </div>
    </aside>
  );
}

export default Callout;
