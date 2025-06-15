'use client';

import React, { useState } from 'react';
import Image from 'next/image';
import Lightbox from "yet-another-react-lightbox";
import "yet-another-react-lightbox/styles.css";
// Optional: Import lightbox plugins if needed (e.g., Thumbnails, Zoom)
// import Thumbnails from "yet-another-react-lightbox/plugins/thumbnails";
// import Zoom from "yet-another-react-lightbox/plugins/zoom";
// import "yet-another-react-lightbox/plugins/thumbnails.css";

interface SpeciesImageGalleryProps {
  speciesName: string;
  mainImageUrl: string | null;
  allImageUrls: string[];
}

const SpeciesImageGallery: React.FC<SpeciesImageGalleryProps> = ({ 
  speciesName, 
  mainImageUrl, 
  allImageUrls 
}) => {
  const [open, setOpen] = useState(false);
  const [index, setIndex] = useState(0);

  // Create the slides array for the lightbox
  const slides = allImageUrls.map(url => ({ src: url }));

  // Function to open the lightbox at a specific image index
  const openLightbox = (imageIndex: number) => {
    setIndex(imageIndex);
    setOpen(true);
  };

  return (
    <div>
      {/* Main Image - Make it clickable */}
      <div 
        className="relative aspect-[4/3] bg-gray-200 dark:bg-gray-700 rounded-lg overflow-hidden mb-4 cursor-pointer hover:opacity-90 transition-opacity"
        onClick={() => mainImageUrl ? openLightbox(allImageUrls.indexOf(mainImageUrl)) : null} // Open lightbox at main image index
      >
        {mainImageUrl ? (
          <Image
            src={mainImageUrl} 
            alt={speciesName}
            fill
            style={{ objectFit: 'contain' }}
            sizes="(max-width: 1024px) 100vw, 66vw"
            priority
          />
        ) : (
          <div className="flex items-center justify-center h-full">
            <span className="text-gray-500">Image not available</span>
          </div>
        )}
      </div>
      
      {/* Additional Images Thumbnails - Make them clickable */}
      {allImageUrls.length > 1 && (
        <div className="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 lg:grid-cols-7 gap-2">
          {allImageUrls.map((imgUrl, idx) => (
            <div 
              key={idx} 
              className="relative aspect-square bg-gray-200 dark:bg-gray-700 rounded overflow-hidden cursor-pointer hover:opacity-80 transition-opacity"
              onClick={() => openLightbox(idx)} // Open lightbox at this thumbnail's index
            >
              <Image
                src={imgUrl}
                alt={`${speciesName} (${idx + 1})`}
                fill
                style={{ objectFit: 'contain' }}
                sizes="(max-width: 640px) 25vw, (max-width: 768px) 20vw, (max-width: 1024px) 16.6vw, 14vw"
              />
            </div>
          ))}
        </div>
      )}

      {/* Lightbox Component */}
      <Lightbox
        open={open}
        close={() => setOpen(false)}
        slides={slides}
        index={index}
        // Optional plugins:
        // plugins={[Thumbnails, Zoom]}
      />
    </div>
  );
};

export default SpeciesImageGallery; 