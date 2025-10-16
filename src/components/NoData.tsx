export function NoData({ text }: { text?: string }) {
  return <p className="text-gray-500">{text || "No data available"}</p>;
}
