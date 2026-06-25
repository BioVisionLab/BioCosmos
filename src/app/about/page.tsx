import React from "react";
import Link from "next/link";

const coreTeam = [
  {
    name: "Arthur Porto",
    role: "Principal Investigator",
    affiliation: "Florida Museum of Natural History, University of Florida",
    description:
      "Project lead for BioCosmos, with a focus on computer vision, biodiversity AI, organismal biology, and museum-scale research infrastructure.",
  },
  {
    name: "Heru Handika",
    role: "Lead Developer",
    affiliation: "Florida Museum of Natural History, University of Florida",
    description:
      "Main developer of the BioCosmos platform, including core software infrastructure, data integration, search systems, deployment workflows, and user-facing tools for AI-powered biodiversity discovery.",
  },
  {
    name: "Jose Fortes",
    role: "Co-Principal Investigator",
    affiliation: "University of Florida",
    description:
      "Co-PI of the UF AI\u00B2 award supporting BioCosmos, with expertise in natural language processing, AI systems, and research computing infrastructure.",
  },
  {
    name: "Venkata Yarava",
    role: "DevOps and Research Computing",
    affiliation: "University of Florida",
    description:
      "Supports deployment, infrastructure, system administration, and the computational environment needed to run BioCosmos as a scalable research platform.",
  },
  {
    name: "Michael Elliot",
    role: "Large Language Models",
    affiliation: "University of Florida",
    description:
      "Contributes to the language-model components of BioCosmos, including natural-language querying, model integration, and AI-assisted interaction with biodiversity data.",
  },
  {
    name: "Moritz L\u00FCrig",
    role: "Butterfly Dataset Development",
    affiliation: "University of Florida / BioCosmos collaborator",
    description:
      "Led the assembly, cleaning, and organization of the butterfly image dataset that serves as a foundational resource for developing, evaluating, and demonstrating BioCosmos.",
  },
  {
    name: "Oliver Dobon",
    role: "Machine Learning Researcher",
    affiliation: "BioCosmos / BioVision Lab",
    description:
      "Contributes to machine-learning development and evaluation for fine-grained biological retrieval in BioCosmos.",
  },
  {
    name: "Kira Nitchtawitz",
    role: "Undergraduate Researcher",
    affiliation: "Florida Museum of Natural History, University of Florida",
    description:
      "Contributes to the design of the web layout, data integration, and visualization.",
  },
];

const haagCollaborators = [
  {
    name: "Breanna \u201CBree\u201D Shi",
    affiliation:
      "Georgia Institute of Technology / Human-Augmented Analytics Group",
    description:
      "Instrumental in organizing and guiding the HAAG contribution to BioCosmos.",
  },
  {
    name: "Thomas Deatherage",
    affiliation:
      "Georgia Institute of Technology / Human-Augmented Analytics Group",
    description: "Contributed to the initial BioCosmos prototyping effort.",
  },
  {
    name: "Romouald Dombrovski",
    affiliation:
      "Georgia Institute of Technology / Human-Augmented Analytics Group",
    description: "Contributed to the initial BioCosmos prototyping effort.",
  },
  {
    name: "Elan Grossman",
    affiliation:
      "Georgia Institute of Technology / Human-Augmented Analytics Group",
    description: "Contributed to the initial BioCosmos prototyping effort.",
  },
];

export default function AboutPage() {
  return (
    <main className="max-w-4xl mx-auto px-6 py-12">
      <Link
        href="/"
        className="text-pacific-blue-600 hover:underline text-sm"
      >
        &larr; Back to Home
      </Link>

      {/* Header */}
      <h1 className="text-4xl font-bold mt-6 mb-4">About LepiVerse</h1>
      <p className="text-lg text-deep-mocha-700 dark:text-deep-mocha-300 mb-8">
        LepiVerse is the Lepidoptera-focused interface powered by{" "}
        <span className="font-semibold">BioCosmos</span>, an AI engine for
        exploring biodiversity through images, traits, taxonomy, geography,
        and natural-language search.
      </p>

      {/* Introduction */}
      <section className="mb-12 space-y-4 text-deep-mocha-700 dark:text-deep-mocha-300 leading-relaxed">
        <p>
          Natural history collections contain an extraordinary record of life on
          Earth. They preserve specimens, images, labels, traits, geographic
          records, and taxonomic knowledge accumulated over centuries. Yet much
          of this information remains difficult to search, compare, and
          synthesize at scale. BioCosmos is being developed to make biodiversity
          data more usable by connecting museum specimens, biological images,
          taxonomic information, traits, and occurrence records through modern
          machine learning and interactive web tools.
        </p>
        <p>
          The project began with butterflies as a model system. Butterflies
          provide a visually rich and scientifically important group for
          developing tools for image-based search, trait discovery, fine-grained
          biological retrieval, and interactive exploration of biodiversity.
          LepiVerse is the interface that brings these capabilities to the
          Lepidoptera community, with BioCosmos as the engine behind it. From
          this foundation,
          BioCosmos aims to support broader discovery across organismal groups
          and natural history collections.
        </p>
      </section>

      {/* What BioCosmos does */}
      <section className="mb-12">
        <h2 className="text-2xl font-semibold mb-4">What BioCosmos does</h2>
        <p className="text-deep-mocha-700 dark:text-deep-mocha-300 leading-relaxed mb-4">
          BioCosmos helps users move through biodiversity data in ways that are
          closer to how researchers, students, and collection users actually ask
          questions. Instead of searching only by scientific name or catalog
          fields, users can explore organisms by visual similarity, color,
          morphology, traits, geography, and natural-language descriptions.
        </p>
        <p className="text-deep-mocha-700 dark:text-deep-mocha-300 mb-3">
          The platform is being developed to support questions such as:
        </p>
        <ul className="list-disc list-inside space-y-1 text-deep-mocha-700 dark:text-deep-mocha-300 ml-2">
          <li>Which species look visually similar to this specimen?</li>
          <li>
            What butterflies are blue and occur in the United States?
          </li>
          <li>
            Which specimens match a particular visual pattern, trait, or
            ecological context?
          </li>
          <li>
            How can museum images be organized into useful biological
            neighborhoods?
          </li>
          <li>
            How can AI help researchers discover, curate, and compare
            biodiversity data?
          </li>
        </ul>
        <p className="text-deep-mocha-700 dark:text-deep-mocha-300 leading-relaxed mt-4">
          BioCosmos combines computer vision, vector search, biodiversity
          informatics, and language-model-based query tools to make natural
          history data easier to search, interpret, and reuse.
        </p>
      </section>

      {/* Why it matters */}
      <section className="mb-12">
        <h2 className="text-2xl font-semibold mb-4">Why it matters</h2>
        <div className="space-y-4 text-deep-mocha-700 dark:text-deep-mocha-300 leading-relaxed">
          <p>
            Biodiversity science increasingly depends on the ability to work
            across large, heterogeneous datasets: specimen images, occurrence
            records, taxonomic databases, trait descriptions, and collection
            metadata. These data are powerful, but they are often scattered
            across systems and difficult to query together.
          </p>
          <p>
            BioCosmos addresses this gap by building AI infrastructure for
            organismal biology. Its goal is not to replace expert knowledge, but
            to amplify it: helping researchers find patterns, generate
            hypotheses, identify overlooked specimens, and move more fluidly
            between images, names, traits, and places.
          </p>
        </div>
      </section>

      {/* People */}
      <section className="mb-12">
        <h2 className="text-2xl font-semibold mb-6">People</h2>

        {/* Core team */}
        <h3 className="text-xl font-medium mb-4">Core team</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
          {coreTeam.map((person) => (
            <div
              key={person.name}
              className="rounded-lg border border-deep-mocha-200 dark:border-deep-mocha-700 bg-white/50 dark:bg-deep-mocha-800/50 p-4"
            >
              <h4 className="font-semibold text-deep-mocha-900 dark:text-deep-mocha-100">
                {person.name}
              </h4>
              <p className="text-sm font-medium text-pacific-blue-600 dark:text-pacific-blue-400">
                {person.role}
              </p>
              <p className="text-xs text-deep-mocha-500 dark:text-deep-mocha-400 mb-2">
                {person.affiliation}
              </p>
              <p className="text-sm text-deep-mocha-600 dark:text-deep-mocha-300">
                {person.description}
              </p>
            </div>
          ))}
        </div>

        {/* HAAG collaborators */}
        <h3 className="text-xl font-medium mb-2">
          Georgia Tech and HAAG collaborators
        </h3>
        <p className="text-sm text-deep-mocha-700 dark:text-deep-mocha-300 mb-4">
          BioCosmos benefited from early prototyping support from researchers in
          Georgia Tech&apos;s Human-Augmented Analytics Group (HAAG). HAAG
          researchers were primarily involved in the initial prototyping phase of
          the project, helping shape early work on data ingestion, frontend and
          backend infrastructure, vector search, deployment, model evaluation,
          and LLM-assisted query control.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
          {haagCollaborators.map((person) => (
            <div
              key={person.name}
              className="rounded-lg border border-deep-mocha-200 dark:border-deep-mocha-700 bg-white/50 dark:bg-deep-mocha-800/50 p-4"
            >
              <h4 className="font-semibold text-deep-mocha-900 dark:text-deep-mocha-100">
                {person.name}
              </h4>
              <p className="text-xs text-deep-mocha-500 dark:text-deep-mocha-400 mb-2">
                {person.affiliation}
              </p>
              <p className="text-sm text-deep-mocha-600 dark:text-deep-mocha-300">
                {person.description}
              </p>
            </div>
          ))}
        </div>

        {/* Additional contributors */}
        <p className="text-sm text-deep-mocha-700 dark:text-deep-mocha-300 italic">
          BioCosmos is an active research and software-development effort, with
          contributions from students, developers, and researchers working on
          model evaluation, user interfaces, data pipelines, image embeddings,
          trait discovery, and biological search.
        </p>
      </section>

      {/* Funding and support */}
      <section className="mb-12">
        <h2 className="text-2xl font-semibold mb-4">Funding and support</h2>
        <div className="space-y-4 text-deep-mocha-700 dark:text-deep-mocha-300">
          <div className="rounded-lg border border-deep-mocha-200 dark:border-deep-mocha-700 bg-white/50 dark:bg-deep-mocha-800/50 p-4">
            <h4 className="font-semibold">
              University of Florida AI&sup2; Seed Award
            </h4>
            <p className="text-sm mt-1">
              BioCosmos: A Foundational Multimodal AI Model for Biodiversity
            </p>
            <p className="text-xs text-deep-mocha-500 dark:text-deep-mocha-400 mt-1">
              2024&ndash;2026 &middot; PI: Arthur Porto &middot; Co-PI: Jose
              Fortes
            </p>
          </div>
          <div className="rounded-lg border border-deep-mocha-200 dark:border-deep-mocha-700 bg-white/50 dark:bg-deep-mocha-800/50 p-4">
            <h4 className="font-semibold">
              University of Florida Biodiversity Institute
            </h4>
            <p className="text-sm mt-1">
              Support for biodiversity AI, natural history collections research,
              and the development of computational infrastructure for studying
              biological diversity at scale.
            </p>
          </div>
          <div className="rounded-lg border border-deep-mocha-200 dark:border-deep-mocha-700 bg-white/50 dark:bg-deep-mocha-800/50 p-4">
            <h4 className="font-semibold">
              University of Florida Research Computing
            </h4>
            <p className="text-sm mt-1">
              Hosting and research-computing support for the BioCosmos platform.
            </p>
          </div>
        </div>
      </section>

      {/* Data and responsible use */}
      <section className="mb-12">
        <h2 className="text-2xl font-semibold mb-4">
          Data and responsible use
        </h2>
        <div className="space-y-4 text-deep-mocha-700 dark:text-deep-mocha-300 leading-relaxed">
          <p>
            BioCosmos is built to support research, education, and biodiversity
            discovery. The platform integrates public biodiversity data, museum
            specimen information, and biological images where available. Because
            AI models can reflect biases in training data, sampling, taxonomy,
            geography, and image availability, BioCosmos should be used as a tool
            for exploration and hypothesis generation rather than as a substitute
            for expert verification.
          </p>
          <p>
            We welcome feedback from biodiversity researchers, collection
            managers, students, educators, and developers interested in improving
            AI tools for natural history collections.
          </p>
        </div>
      </section>

      {/* Contact */}
      <section className="mb-8">
        <h2 className="text-2xl font-semibold mb-4">Contact</h2>
        <p className="text-deep-mocha-700 dark:text-deep-mocha-300 mb-2">
          For questions about BioCosmos, collaborations, or research use, please
          contact:
        </p>
        <div className="rounded-lg border border-deep-mocha-200 dark:border-deep-mocha-700 bg-white/50 dark:bg-deep-mocha-800/50 p-4">
          <p className="font-semibold">Arthur Porto</p>
          <p className="text-sm text-deep-mocha-600 dark:text-deep-mocha-300">
            Florida Museum of Natural History, University of Florida
          </p>
          <a
            href="mailto:arthur.porto@ufl.edu"
            className="text-sm text-pacific-blue-600 dark:text-pacific-blue-400 hover:underline"
          >
            arthur.porto@ufl.edu
          </a>
        </div>
      </section>
    </main>
  );
}
