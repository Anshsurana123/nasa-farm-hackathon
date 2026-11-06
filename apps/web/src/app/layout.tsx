import type { Metadata, Viewport } from "next";
import { Fraunces, JetBrains_Mono, Plus_Jakarta_Sans, Space_Grotesk } from "next/font/google";
import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";
import { I18nProvider } from "@/i18n";
import { FieldProvider } from "@/context/FieldContext";

const geistSans = Plus_Jakarta_Sans({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const geistMono = JetBrains_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const display = Space_Grotesk({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
});

const serif = Fraunces({
  variable: "--font-serif",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "TerraLoop — NASA Earth Observation & Agronomic Decision System",
  description:
    "Interactive multi-page crop rotation, soil stratigraphy, and aquifer conservation platform powered by NASA POWER, SMAP, GRACE-FO, FIRMS, ISRIC SoilGrids, and FAO AquaCrop.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#060b16" },
    { media: "(prefers-color-scheme: light)", color: "#f4f7fb" },
  ],
};

// Applies the saved/preferred theme before first paint to avoid a light/dark flash.
const themeScript = `(function(){try{var s=localStorage.getItem("theme");var d=s?s==="dark":true;document.documentElement.classList.toggle("dark",d);}catch(e){document.documentElement.classList.add("dark");}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`dark ${geistSans.variable} ${geistMono.variable} ${display.variable} ${serif.variable} h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-full flex flex-col bg-background text-foreground selection:bg-emerald-500/30">
        <div className="app-backdrop" aria-hidden="true" />
        <I18nProvider>
          <FieldProvider>{children}</FieldProvider>
        </I18nProvider>
      </body>
    </html>
  );
}
