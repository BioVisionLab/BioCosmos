import { GbifAttribution } from "@/components/Attribution";
import { TaxonomyData } from "@/lib/speciesData";

export function SpeciesClassification({
  taxonomyData,
}: {
  taxonomyData: TaxonomyData | null;
}) {
  if (!taxonomyData) {
    return (
      <p className="text-gray-500 dark:text-gray-400">
        No classification data available.
      </p>
    );
  }

  return (
    <div className="-mt-1 bg-gradient-to-b from-white/50 to-white/30 dark:from-gray-800/50 dark:to-gray-800/30 p-4 rounded-xl shadow">
      <h2 className="text-2xl font-semibold mb-2">Classification</h2>
      <table className="text-sm text-gray-700 dark:text-gray-300 w-full min-w-[350px]">
        <tbody>
          <tr>
            <td className="font-medium w-36 pr-2 align-top">Kingdom</td>
            <td className="break-all">
              : {taxonomyData?.kingdom ?? "Unknown"}
            </td>
          </tr>
          <tr>
            <td className="font-medium w-36 pr-2 align-top">Phylum</td>
            <td className="break-all">: {taxonomyData?.phylum ?? "Unknown"}</td>
          </tr>
          <tr>
            <td className="font-medium w-36 pr-2 align-top">Class</td>
            <td className="break-all">: {taxonomyData?.class ?? "Unknown"}</td>
          </tr>
          <tr>
            <td className="font-medium w-36 pr-2 align-top">Order</td>
            <td className="break-all">: {taxonomyData?.order ?? "Unknown"}</td>
          </tr>
          <tr>
            <td className="font-medium w-36 pr-2 align-top">Family</td>
            <td className="break-all">: {taxonomyData?.family ?? "Unknown"}</td>
          </tr>
          <tr>
            <td className="font-medium w-36 pr-2 align-top">Genus</td>
            <td className="break-all">
              : <i className="italic">{taxonomyData?.genus ?? "Unknown"}</i>
            </td>
          </tr>
          <tr>
            <td className="font-medium w-36 pr-2 align-top">Species</td>
            <td className="break-all">
              : <i className="italic">{taxonomyData?.species ?? "Unknown"}</i>
            </td>
          </tr>
          <tr>
            <td className="font-medium w-36 pr-2 align-top">Authorship</td>
            <td className="break-all">
              : {taxonomyData?.authorship ?? "Unknown"}
            </td>
          </tr>
          <tr>
            <td className="font-medium w-36 pr-2 align-top my-2">
              Taxonomic Status
            </td>
            <td className="break-all">
              : {taxonomyData?.taxonomicStatus ?? "Unknown"}
            </td>
          </tr>
        </tbody>
      </table>
      <GbifAttribution />
    </div>
  );
}
