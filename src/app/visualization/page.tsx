'use client'; // Make this a Client Component

import React from 'react';
import dynamic from 'next/dynamic'; // Import dynamic

// Dynamically import the client component with SSR disabled
// This is now allowed because the parent (this file) is a Client Component
const VisualizationMapClient = dynamic(() => import('@/components/VisualizationMapClient'), {
    ssr: false,
    loading: () => <div className="p-4">Loading map...</div> // Optional loading indicator
});

export default function VisualizationPage() {
    return (
        <section>
            <h1 className="text-3xl font-bold mb-6">Dataset Visualization</h1>
            {/* Render the dynamically imported client component */}
            <VisualizationMapClient />
        </section>
    );
} 