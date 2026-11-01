import { intermediateRankRoute } from "@/components/HigherTaxonPage";

// See the note on the family page: the thirty-day cache is on the fetch, not
// on this segment, and this flag does not defeat it.
export const dynamic = "force-dynamic";

const route = intermediateRankRoute("tribe");

export const generateMetadata = route.generateMetadata;

export default route.Page;
