export default function GalleryLayout({ children }: { children: React.ReactNode }) {
  // Use no special background so the gallery inherits the global site layout
  return <>{children}</>;
}
