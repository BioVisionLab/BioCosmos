import { Lightbulb } from "lucide-react";

function Tips({ message }: { message: string }) {
  return (
    <div className="flex my-2 items-center gap-1 border-l-8 border border-deep-mocha-600/40 bg-deep-mocha-100/10 dark:bg-deep-mocha-800/20 rounded-lg p-2 w-fit">
      <div className="flex-shrink-0">
        <Lightbulb
          className="h-4 w-4 stroke-deep-mocha-500"
          aria-hidden="true"
        />
      </div>
      <div className="text-xs text-deep-mocha-500">
        <p>{message}</p>
      </div>
    </div>
  );
}

export default Tips;
