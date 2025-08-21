// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { getGenusList, type GenusSummary } from '@/lib/speciesData';
import HomeClient from '@/components/HomeClient'; // Reuse HomeClient for genus grid
import Link from 'next/link';

interface FamilyPageProps {
  params: {
    familyName: string; // This comes from the folder name [familyName]
  };
}

export default async function FamilyPage({ params }: FamilyPageProps) {
  const { familyName } = params;
  const decodedFamilyName = decodeURIComponent(familyName);

  // Fetch the list of genera for this family
  const genusList = await getGenusList(decodedFamilyName);

  return (
    <section>
      {/* Breadcrumbs */}
      <nav className="text-sm mb-4 text-gray-600 dark:text-gray-400 flex items-center gap-2">
        <Link href="/" className="hover:underline">Home</Link>
        <span>&gt;</span>
        <span className="font-semibold text-gray-800 dark:text-gray-200">{decodedFamilyName}</span>
      </nav>

      <h1 className="text-3xl font-bold mb-6">
        Genera in {decodedFamilyName}
      </h1>

      {/* Render the HomeClient component to display the genus grid */}
      {/* It already expects initialGenusList */}
      <HomeClient initialGenusList={genusList} />

    </section>
  );
} 