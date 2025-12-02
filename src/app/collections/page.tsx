import React from "react";
import Link from "next/link";

export default function CollectionsPage() {
  return (
    <main className="max-w-4xl mx-auto p-8">
      <h1 className="text-3xl font-bold mb-4">Collections</h1>
      <p className="mb-6 text-gray-700 dark:text-gray-300">
        This is a placeholder Collections page.
      </p>
      <Link href="/" className="text-teal-600 hover:underline">
        ← Back to Home
      </Link>
    </main>
  );
}
