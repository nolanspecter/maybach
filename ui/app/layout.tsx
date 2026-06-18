import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Maybach",
  description: "Autonomous agent system",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased font-sans">{children}</body>
    </html>
  );
}
