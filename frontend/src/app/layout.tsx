import type { Metadata } from "next";
import { Bricolage_Grotesque, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { ThemeProvider } from "@/lib/theme-context";

const bricolage = Bricolage_Grotesque({
  variable: "--font-brand",
  subsets: ["latin"],
  display: "swap",
});

const jetbrains = JetBrains_Mono({
  variable: "--font-mono-jb",
  subsets: ["latin"],
  display: "swap",
});

const SITE = "https://kaia-ai.duckdns.org";

const DESCRIPTION =
  "A personal AI assistant that handles your calendar, email and documents — and calls your phone.";

export const metadata: Metadata = {
  title: "Kaia",
  description: DESCRIPTION,
};

const noFlash = `
try {
  var t = localStorage.getItem('kaia-theme');
  if (t) document.documentElement.setAttribute('data-theme', t);
} catch (e) {}
`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" data-theme="light" className={`${bricolage.variable} ${jetbrains.variable} h-full`}>
      <head>
        {/* Written as plain tags rather than via the metadata API: an
            openGraph block there forces runtime metadata on /agents/[id],
            which cacheComponents refuses to prerender. */}
        <meta property="og:type" content="website" />
        <meta property="og:site_name" content="Kaia" />
        <meta property="og:url" content={SITE} />
        <meta property="og:title" content="Kaia — your personal AI assistant" />
        <meta property="og:description" content={DESCRIPTION} />
        <meta property="og:image" content={`${SITE}/og.png`} />
        <meta property="og:image:width" content="1200" />
        <meta property="og:image:height" content="630" />
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="Kaia — your personal AI assistant" />
        <meta name="twitter:description" content={DESCRIPTION} />
        <meta name="twitter:image" content={`${SITE}/og.png`} />
        <meta name="theme-color" content="#FDF7F4" />
        <script dangerouslySetInnerHTML={{ __html: noFlash }} />
      </head>
      <body className="min-h-full">
        <ThemeProvider>
          <AuthProvider>{children}</AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
