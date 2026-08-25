import {
  CrossRefLink,
  GbifDataSourceInfo,
  LepTraitDataSourceInfo,
  NcbiAttribution,
  NcbiDataSourceInfo,
} from "@/components/Attribution";
import Link from "next/link";

export default function ResourcesPage() {
  return (
    <main className="max-w-7xl mx-auto p-8">
      <h1 className="text-3xl font-bold mb-4">
        Resources and Data Usage Attribution
      </h1>
      <Link href="/" className="text-pacific-blue-600 hover:underline">
        ← Back to Home
      </Link>
      <section className="my-12 space-y-4 text-deep-mocha-700 dark:text-deep-mocha-300 leading-relaxed">
        <h2 className="text-2xl font-semibold">Primary Data</h2>
        <p>
          Primary data consists of butterfly images and their associated
          metadata. These datasets are courtesy of museum providers and our
          research collaborators. We downloaded the metadata from data
          agregators (mainly{" "}
          <a
            href="https://www.gbif.org/"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-blue-700"
          >
            GBIF
          </a>
          ,{" "}
          <a
            href="https://idigbio.gbif.us/"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-blue-700"
          >
            iDigBio
          </a>
          ,{" "}
          <a
            href="https://ecdysis.org/"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-blue-700"
          >
            Ecdysis
          </a>
          , and{" "}
          <a
            href="https://scan-all-bugs.org/"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-blue-700"
          >
            SCANBUGS
          </a>
          ). The images were downloaded directly from the institutions through
          the links provided in the metadata.
        </p>
      </section>
      <section className="my-12 space-y-4 text-deep-mocha-700 dark:text-deep-mocha-300 leading-relaxed">
        <h2 className="text-2xl font-semibold">Realtime Occurrence Data</h2>
        <p>
          In addition to the primary data, we show realtime occurrence data in
          the species overview section. This data is queried directly from GBIF
          using the species name.
        </p>
        <GbifDataSourceInfo />
      </section>
      <section className="my-12 space-y-4 text-deep-mocha-700 dark:text-deep-mocha-300 leading-relaxed">
        <h2 className="text-2xl font-semibold">Trait Datasets</h2>
        <LepTraitDataSourceInfo />
      </section>
      <section className="my-12 space-y-4 text-deep-mocha-700 dark:text-deep-mocha-300 leading-relaxed">
        <h2 className="text-2xl font-semibold">Genetic Data</h2>
        <NcbiDataSourceInfo />
      </section>
      <section className="my-12 space-y-4 text-deep-mocha-700 dark:text-deep-mocha-300 leading-relaxed">
        <h2 className="text-2xl font-semibold">Wikipedia</h2>
        <p>
          We use{" "}
          <a
            href="https://en.wikipedia.org/wiki/Main_Page"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-blue-700"
          >
            Wikipedia
          </a>{" "}
          as a supplementary source of information for the species. See content{" "}
          <a
            href="https://en.wikipedia.org/wiki/Wikipedia:Copyrights"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-blue-700"
          >
            license
          </a>
          .
        </p>
      </section>
      <section className="my-12 space-y-4 text-deep-mocha-700 dark:text-deep-mocha-300 leading-relaxed">
        <h2 className="text-2xl font-semibold">Literature</h2>
        <p>
          The literature data is obtained from <CrossRefLink />. BioCosmos
          filter the data to get the most relevant information for literature
          lists.
        </p>
      </section>
    </main>
  );
}
