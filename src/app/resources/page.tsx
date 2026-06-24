import React from "react";
import Link from "next/link";

export default function ResourcesPage() {
  return (
    <main className="max-w-4xl mx-auto p-8">
      <h1 className="text-3xl font-bold mb-4">Resources</h1>
      <p className="mb-6 text-deep-mocha-700 dark:text-deep-mocha-300">
        This is a placeholder Resources page.
      </p>
      <Link href="/" className="text-pacific-blue-600 hover:underline">
        ← Back to Home
      </Link>
    </main>
  );
}
