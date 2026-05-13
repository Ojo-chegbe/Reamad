import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "The Gatekeeper | Soloa AI",
  description: "Soloa AI social listening and reply intelligence",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
