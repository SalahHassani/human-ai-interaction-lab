import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "HAI-Lab | Human–AI Interaction Research Platform",
  description:
    "Controlled experimental platform for human–AI interaction studies, telemetry, and reproducible analysis.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
            <Link href="/" className="flex items-center gap-2.5">
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-slate-900 text-sm font-bold text-white">
                H
              </span>
              <div>
                <span className="font-semibold tracking-tight text-slate-900">
                  HAI-Lab
                </span>
                <span className="ml-2 hidden text-xs text-slate-500 sm:inline">
                  Human–AI Interaction Lab
                </span>
              </div>
            </Link>
            <nav className="flex items-center gap-4 text-sm font-medium">
              <Link
                href="/study"
                className="text-slate-600 transition hover:text-slate-900"
              >
                Participant Entry
              </Link>
              <Link
                href="/dashboard"
                className="rounded-lg bg-slate-900 px-3.5 py-2 text-white transition hover:bg-slate-800"
              >
                Researcher Portal
              </Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
      </body>
    </html>
  );
}