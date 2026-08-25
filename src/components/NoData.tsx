export function NoData({ text }: { text?: string }) {
  return <p className="text-deep-mocha-500">{text || "No data available"}</p>;
}
