'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useRouter } from 'next/navigation'; // Use App Router navigation
import { ThemeToggle } from './ThemeToggle';
import { Search, FlaskConical, Loader2 } from 'lucide-react'; // Import icons and Loader2

// Define the type for the semantic result object from the Python service
interface SemanticResultItem {
    species_folder: string;
    best_image_filename: string;
}

const LOCAL_STORAGE_KEY = 'searchMode'; // Key for localStorage

export default function HeaderClient() {
  // Initialize state to default (false) to match server render
  const [isSemantic, setIsSemantic] = useState(false); 
  const [isMounted, setIsMounted] = useState(false); // Track client mount status
  const [searchTerm, setSearchTerm] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const router = useRouter();

  // Effect runs only on the client after mount
  useEffect(() => {
    // Read from localStorage and update state
    const storedMode = localStorage.getItem(LOCAL_STORAGE_KEY);
    setIsSemantic(storedMode === 'semantic');
    // Mark as mounted
    setIsMounted(true); 
  }, []); // Empty dependency array ensures it runs only once on mount

  // Effect to update localStorage when state changes (dependent on isMounted)
  useEffect(() => {
      // Only write to localStorage after initial mount & state hydration
      if (isMounted) { 
          localStorage.setItem(LOCAL_STORAGE_KEY, isSemantic ? 'semantic' : 'text');
      }
  }, [isSemantic, isMounted]);

  const handleSearchSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const query = searchTerm.trim();
    if (!query) return;

    setIsSearching(true);
    setSearchError(null);

    if (isSemantic) {
      try {
        // Call the new backend route for semantic search
        const response = await fetch(`/api/semantic-search?q=${encodeURIComponent(query)}`);
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || `Semantic search failed with status ${response.status}`);
        }
        const results: SemanticResultItem[] = await response.json(); // Type the result correctly

        // Navigate to search page with identifiers
        // Pass the *JSON stringified* array as the query param
        if (results.length > 0) {
            router.push(`/search?ids=${encodeURIComponent(JSON.stringify(results))}&mode=semantic`); 
        } else {
            // Handle case where semantic search returns no results
            setSearchError("No similar species found for the semantic query.");
            console.log("Semantic search returned empty results.");
        }

      } catch (err) {
        console.error("Semantic search error:", err);
        setSearchError(err instanceof Error ? err.message : "An unknown semantic search error occurred.");
      } finally {
        setIsSearching(false);
      }
    } else {
      // Standard text search navigation
      router.push(`/search?q=${encodeURIComponent(query)}&mode=text`); 
      // No need for loading state here as navigation is immediate
      // If we wanted loading, we'd need to handle it on the results page
      setIsSearching(false); 
    }
  };

  const toggleSearchMode = () => {
    // State update will trigger the useEffect to save to localStorage
    setIsSemantic(!isSemantic);
    setSearchTerm(''); // Clear search term on mode switch
    setSearchError(null); // Clear errors
  };

  return (
    <header className="bg-white dark:bg-deep-mocha-800 shadow-md sticky top-0 z-10">
      <nav className="container mx-auto px-4 py-3 flex justify-between items-center gap-4">
        {/* Logo Link */}
        <Link href="/" legacyBehavior={false} className="flex-shrink-0">
          <div className="flex items-center gap-2 cursor-pointer">
            <Image 
              src="/leaflet/images/logo.png"
              alt="biocosmos logo"
              width={32}
              height={32}
              className="h-8 w-8"
            />
            <span className="text-2xl font-bold text-deep-mocha-900 dark:text-deep-mocha-100 font-poppins whitespace-nowrap">
              Biocosmos
            </span>
          </div>
        </Link>
        
        {/* Search Form & Toggle */}
        <div className="flex-grow min-w-0">
          <form onSubmit={handleSearchSubmit} className="flex items-center gap-2">
            <div className="relative flex-grow">
              <input
                type="text"
                placeholder={isMounted && isSemantic ? "Semantic search (e.g., orange butterfly with black lines)" : "Search species name..."}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                disabled={isSearching} // Disable input while searching
                className={`w-full px-4 py-2 rounded-md border border-deep-mocha-300 dark:border-deep-mocha-700 bg-deep-mocha-50 dark:bg-deep-mocha-700 focus:outline-none focus:ring-2 focus:ring-green-500 min-w-0 ${isSearching ? 'opacity-50' : ''}`}
              />
              {/* Loading indicator inside input */}
              {isSearching && (
                <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
                  <Loader2 className="h-5 w-5 text-deep-mocha-400 animate-spin" />
                </div>
              )}
            </div>
            <button
              type="button"
              onClick={toggleSearchMode}
              disabled={isSearching || !isMounted} // Disable until mounted
              title={!isMounted ? "Loading mode..." : isSemantic ? "Switch to Text Search" : "Switch to Semantic Search"}
              className={`flex-shrink-0 p-2 rounded-md hover:bg-deep-mocha-200 dark:hover:bg-deep-mocha-700 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-green-500 ${isSemantic ? 'bg-green-100 dark:bg-green-900' : ''} disabled:opacity-50 disabled:cursor-not-allowed ${!isMounted ? 'opacity-50' : ''}`}
            >
              {!isMounted ? (
                <Search className="h-5 w-5 text-deep-mocha-400" />
              ) : isSemantic ? (
                <FlaskConical className="h-5 w-5 text-green-700 dark:text-green-300" />
              ) : (
                <Search className="h-5 w-5 text-deep-mocha-600 dark:text-deep-mocha-400" />
              )}
            </button>
            {/* Hidden submit button */}
            <button type="submit" className="hidden">Search</button>
          </form>
           {/* Display Search Error */} 
           {searchError && (
             <p className="text-xs text-burnt-peach-500 mt-1">Error: {searchError}</p>
           )}
        </div>

        {/* Nav Links & Profile */}
        <div className="flex items-center space-x-4 flex-shrink-0">
          <Link href="/visualization" legacyBehavior={false}>
            <span className="hover:text-green-600 dark:hover:text-green-400 cursor-pointer whitespace-nowrap">Explore</span>
          </Link>
          <a href="#" className="hover:text-green-600 dark:hover:text-green-400 whitespace-nowrap">Collections</a>
          {/* User Profile Icon Placeholder */}
          <div className="w-8 h-8 bg-deep-mocha-400 rounded-full flex-shrink-0"></div>
          <ThemeToggle />
        </div>
      </nav>
    </header>
  );
} 