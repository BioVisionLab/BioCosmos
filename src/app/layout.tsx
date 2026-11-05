import type { Metadata } from "next";
import { Overpass, Source_Code_Pro, Source_Sans_3 } from "next/font/google";
import "./globals.css";
import { ColReleaseProvider } from "@/components/ColReleaseProvider";
import Layout from "@/components/Layout";
import { ThemeProvider } from "@/components/ThemeProvider";
import { fetchColReleaseLabel } from "@/lib/colRelease";

// The site's three typefaces: Overpass, a technical grotesque, for display
// headings; Source Sans 3 for all other text; and Source Code Pro for specimen
// labels, eyebrows, codes and other monospaced figures. All three are variable
// fonts with true italics, which scientific names need, and all three draw ♂
// and ♀ themselves.
const overpass = Overpass({
  subsets: ["latin"],
  style: ["normal", "italic"],
  variable: "--font-overpass",
});

const sourceSans = Source_Sans_3({
  subsets: ["latin"],
  style: ["normal", "italic"],
  variable: "--font-source-sans",
});

const sourceCodePro = Source_Code_Pro({
  subsets: ["latin"],
  style: ["normal", "italic"],
  variable: "--font-source-code-pro",
});

export const metadata: Metadata = {
  title: "Lepiverse",
  description: "A modernize, museum-quality butterfly image platform",
};

// Pages without a fetch of their own are pre-rendered at build time, when
// API_HOST is unset and the Catalogue of Life release falls back to
// COL_RELEASE. Regenerating them hourly brings in the ingested release.
export const revalidate = 3600;

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const colRelease = await fetchColReleaseLabel();

  return (
    <html
      lang="en"
      className={`${overpass.variable} ${sourceSans.variable} ${sourceCodePro.variable}`}
      suppressHydrationWarning
    >
      <body suppressHydrationWarning>
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <ColReleaseProvider release={colRelease}>
            <Layout>{children}</Layout>
          </ColReleaseProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
