import type { Metadata } from "next";
import { IBM_Plex_Mono, Inter } from "next/font/google";
import "./globals.css";
import Layout from "@/components/Layout";
import { ThemeProvider } from "@/components/ThemeProvider";

// Import Poppins font weights
import "@fontsource/poppins/400.css"; // Regular weight
import "@fontsource/poppins/600.css"; // Semibold, for landing headings
import "@fontsource/poppins/700.css"; // Bold weight

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter", // Assign the CSS variable
});

// Specimen labels and section eyebrows on the landing page.
const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-plex-mono",
});

export const metadata: Metadata = {
  title: "Lepiverse",
  description: "A modernize, museum-quality butterfly image platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${plexMono.variable}`}
      suppressHydrationWarning
    >
      <body suppressHydrationWarning>
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <Layout>{children}</Layout>
        </ThemeProvider>
      </body>
    </html>
  );
}
