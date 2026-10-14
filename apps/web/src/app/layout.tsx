import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono, Space_Grotesk } from "next/font/google";
import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";
import { I18nProvider } from "@/i18n";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const display = Space_Grotesk({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
});

export const metadata: Metadata = {
  title: "TerraLoop · NASA Crop Rotation Decision Support",
  description:
    "Crop rotation decision-support tool powered by NASA Earth observations, SoilGrids, and agro-climatic simulation.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#04070d" },
    { media: "(prefers-color-scheme: light)", color: "#f4f6f1" },
  ],
};

// Applies the saved/preferred theme before first paint to avoid a light/dark flash.
const themeScript = `(function(){try{var s=localStorage.getItem("theme");var d=s?s==="dark":true;document.documentElement.classList.toggle("dark",d);}catch(e){document.documentElement.classList.add("dark");}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`dark ${geistSans.variable} ${geistMono.variable} ${display.variable} h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <div className="app-backdrop" aria-hidden="true" />
        <I18nProvider>{children}</I18nProvider>
      </body>
    </html>
  );
}
