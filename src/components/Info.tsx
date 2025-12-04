import { InfoIcon } from "lucide-react";

function Info({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex mb-2 items-center gap-1 border-l-8 border border-gray-600/40 bg-gray-100/10 dark:bg-gray-800/20 rounded-lg p-2 w-fit">
      <div className="flex-shrink-0">
        <InfoIcon className="h-4 w-4 stroke-gray-500" aria-hidden="true" />
      </div>
      <div className="text-xs text-gray-500">{children}</div>
    </div>
  );
}

export default Info;
