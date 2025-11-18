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
    <div className="bg-gradient-to-r from-white/50 to-white/30 dark:from-teal-900/30 dark:to-gray-800/50 rounded-xl backdrop-blur-lg">
      <div className="bg-gradient-to-br from-teal-500/20 to-emerald-300/10 p-4 rounded-t-2xl">
        <h2 className="text-2xl font-semibold">Classification</h2>
      </div>
      <div className="p-4 ml-4">
        <table className="text-sm text-gray-700 dark:text-gray-300 w-full min-w-0">
          <tbody>
            <tr>
              <td className="font-medium pr-1 align-top whitespace-nowrap">
                Kingdom:
              </td>
              <td className="break-words whitespace-normal pl-2">
                {taxonomyData?.kingdom ?? "Unknown"}
              </td>
            </tr>
            <tr>
              <td className="font-medium pr-1 align-top whitespace-nowrap">
                Phylum:
              </td>
              <td className="break-words whitespace-normal pl-2">
                {taxonomyData?.phylum ?? "Unknown"}
              </td>
            </tr>
            <tr>
              <td className="font-medium pr-1 align-top whitespace-nowrap">
                Class:
              </td>
              <td className="break-words whitespace-normal pl-2">
                {taxonomyData?.class ?? "Unknown"}
              </td>
            </tr>
            <tr>
              <td className="font-medium pr-1 align-top whitespace-nowrap">
                Order:
              </td>
              <td className="break-words whitespace-normal pl-2">
                {taxonomyData?.order ?? "Unknown"}
              </td>
            </tr>
            <tr>
              <td className="font-medium pr-1 align-top whitespace-nowrap">
                Family:
              </td>
              <td className="break-words whitespace-normal pl-2">
                {taxonomyData?.family ?? "Unknown"}
              </td>
            </tr>
            <tr>
              <td className="font-medium pr-1 align-top whitespace-nowrap">
                Genus:
              </td>
              <td className="break-words whitespace-normal pl-2">
                {" "}
                <i className="italic">{taxonomyData?.genus ?? "Unknown"}</i>
              </td>
            </tr>
            <tr>
              <td className="font-medium pr-1 align-top whitespace-nowrap">
                Species:
              </td>
              <td className="break-words whitespace-normal pl-2">
                {" "}
                <i className="italic">{taxonomyData?.species ?? "Unknown"}</i>
              </td>
            </tr>
            <tr>
              <td className="font-medium pr-1 align-top whitespace-nowrap">
                Authorship:
              </td>
              <td className="break-words whitespace-normal pl-2">
                {taxonomyData?.authorship ?? "Unknown"}
              </td>
            </tr>
            <tr>
              <td className="font-medium pr-1 align-top whitespace-nowrap my-2">
                Taxonomic Status:
              </td>
              <td className="break-words whitespace-normal pl-2">
                {taxonomyData?.taxonomicStatus ?? "Unknown"}
              </td>
            </tr>
          </tbody>
        </table>

        <GbifAttribution />
      </div>
    </div>
  );
}
