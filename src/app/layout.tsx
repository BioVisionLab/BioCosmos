import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Layout from "@/components/Layout";
import 'leaflet/dist/leaflet.css';
import { ThemeProvider } from "@/components/ThemeProvider";

// Import Poppins font weights
import "@fontsource/poppins/400.css"; // Regular weight
import "@fontsource/poppins/700.css"; // Bold weight

const inter = Inter({ 
  subsets: ["latin"], 
  variable: '--font-inter' // Assign the CSS variable
});

export const metadata: Metadata = {
  title: "biocosmos",
  description: "A personalized, museum-quality biodiversity image platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable}`} suppressHydrationWarning>
      <body>
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
