import type { Metadata } from "next";
import { Overpass, Source_Code_Pro, Source_Sans_3 } from "next/font/google";
import "./globals.css";
import Layout from "@/components/Layout";
import { ThemeProvider } from "@/components/ThemeProvider";

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

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
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
          <Layout>{children}</Layout>
        </ThemeProvider>
      </body>
    </html>
  );
}
