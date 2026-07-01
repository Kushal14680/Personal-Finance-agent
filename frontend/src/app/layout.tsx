import type { Metadata } from "next";
import { Analytics } from '@vercel/analytics/next';
import "./globals.css";

export const metadata: Metadata = {
  title: "FinSense | AI Personal Finance Agent & Advisor",
  description: "Ingest bank statements, automatically categorize items, detect anomalies, audit subscriptions, and receive data-backed savings briefings.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        {children}
        <Analytics />
      </body>
    </html>
  );
}
