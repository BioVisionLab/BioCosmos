import Callout from "@/components/Callout";
import { NotebookPen } from "lucide-react";

/**
 * Caveats on how to read a tab's data. Only render it next to actual results.
 */
function Note({
  children,
  label = "Notes",
}: {
  children: React.ReactNode;
  /** Accessible name for the note. */
  label?: string;
}) {
  return (
    <Callout icon={NotebookPen} label={label}>
      {children}
    </Callout>
  );
}

export default Note;
