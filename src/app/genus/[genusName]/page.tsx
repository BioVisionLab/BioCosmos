import Link from "next/link";

interface GenusPageProps {
  params: Promise<{
    genusName: string;
  }>;
}

export default async function GenusPage({ params }: GenusPageProps) {
  const resolvedParams = await params; // Ensure params are resolved if using Next.js 13+ with async components
  const { genusName } = resolvedParams;
  // Decode the genus name in case it contains URL-encoded characters (like spaces if they ever occur)
  const decodedGenusName = decodeURIComponent(genusName);

  return (
    <section>
      {/* Updated Breadcrumbs */}
      <nav className="text-sm mb-4 text-gray-600 dark:text-gray-400 flex items-center gap-2">
        <Link href="/" className="hover:underline">
          Home
        </Link>
        <span>&gt;</span>
        {/* Link to the Family page */}
        <span className="text-gray-400 italic">Family Name</span>
        <span>&gt;</span>
        <span className="italic font-semibold text-gray-800 dark:text-gray-200">
          {decodedGenusName}
        </span>
      </nav>

      {/* Revert color classes on the genus name in the title */}
      <h1 className="text-3xl font-bold mb-6 italic">
        Species in <span className="italic">{decodedGenusName}</span>
      </h1>

      {/* Render the client component to display the species grid */}
      {/* Pass the fetched species list to the client component */}
      {/* <GenusSpeciesClient initialSpeciesList={speciesList} /> */}
    </section>
  );
}
