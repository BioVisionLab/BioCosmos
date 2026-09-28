import type { Metadata } from "next";
import { JetBrains_Mono, Sora } from "next/font/google";
import "./globals.css";
import Layout from "@/components/Layout";
import { ThemeProvider } from "@/components/ThemeProvider";

// The site's two typefaces: Sora, a geometric sans, for all text, and
// JetBrains Mono for specimen labels, eyebrows, codes and other monospaced
// figures. Both are variable fonts, so every weight the site uses is real.
const sora = Sora({
  subsets: ["latin"],
  variable: "--font-sora",
});

const jetBrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
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
      className={`${sora.variable} ${jetBrainsMono.variable}`}
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
