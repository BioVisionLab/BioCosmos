import HomeClient from "@/components/HomePage"; // Reuse HomeClient for genus grid
import Link from "next/link";

interface FamilyPageProps {
  params: Promise<{
    familyName: string;
  }>;
}

export default async function FamilyPage({ params }: FamilyPageProps) {
  const { familyName } = await params;
  const decodedFamilyName = decodeURIComponent(familyName);

  // Fetch the list of genera for this family
  // const genusList = await getGenusList(decodedFamilyName);

  return (
    <section>
      {/* Breadcrumbs */}
      <nav className="text-sm mb-4 text-deep-mocha-600 dark:text-deep-mocha-400 flex items-center gap-2">
        <Link href="/" className="hover:underline">
          Home
        </Link>
        <span>&gt;</span>
        <span className="font-semibold text-deep-mocha-800 dark:text-deep-mocha-200">
          {decodedFamilyName}
        </span>
      </nav>

      <h1 className="text-3xl font-bold mb-6">Genera in {decodedFamilyName}</h1>

      {/* Render the HomeClient component to display the genus grid */}
      {/* It already expects initialGenusList */}
      {/* <HomeClient initialGenusList={genusList} /> */}
    </section>
  );
}
