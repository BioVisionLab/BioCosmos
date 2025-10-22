import { LepTraits } from "@/lib/leptraits";
import { GeneticData } from "./GeneticData";
import { SpeciesTraits } from "./Traits";
import { NcbiAttribution, NcbiLink } from "@/components/Attribution";

function BiologyPage({
  speciesName,
  traits,
}: {
  speciesName: string;
  traits: LepTraits;
}) {
  return (
    <div>
      <h2 className="text-2xl font-semibold mb-2">Genetics</h2>
      <div className="mb-4">
        <p className="rounded-md border border-yellow-200 bg-yellow-50 px-4 py-3 text-[11px] leading-snug text-gray-700 w-fit">
          Genetic information is fetched automatically from <NcbiLink />. It
          includes only sequenced genes currently available for this species.
        </p>
      </div>
      <GeneticData speciesName={speciesName} />

      <div className="my-8">
        <h2 className="text-2xl font-semibold mb-4">Traits</h2>
        <SpeciesTraits traits={traits} />
      </div>
    </div>
  );
}

export default BiologyPage;
