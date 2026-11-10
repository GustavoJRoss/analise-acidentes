import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

import Header, { BarraAbas } from "@/components/Header";
import { SCRIPT_TEMA, TemaProvider } from "@/components/TemaProvider";
import { CenarioProvider, DadosProvider } from "@/lib/contexto";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "Risco nas rodovias de SC", template: "%s · Risco nas rodovias de SC" },
  description: "Probabilidade de acidentes nas rodovias federais e estaduais de Santa Catarina, por trecho, rodovia, rota, data, período e clima.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#111827" },
  ],
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    // a classe .dark é colocada pelo SCRIPT_TEMA antes da hidratação
    <html lang="pt-BR" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: SCRIPT_TEMA }} />
      </head>
      <body className={`${geistSans.variable} ${geistMono.variable} font-sans antialiased`}>
        <TemaProvider>
          <DadosProvider>
            <CenarioProvider>
              <div className="flex h-dvh flex-col">
                <Header />
                <div className="min-h-0 flex-1">{children}</div>
                <BarraAbas />
              </div>
            </CenarioProvider>
          </DadosProvider>
        </TemaProvider>
      </body>
    </html>
  );
}
