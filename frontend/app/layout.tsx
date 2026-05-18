import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Distilled TI",
  description: "A dynamic personality entertainment system with progressive trait mapping.",
  icons: {
    icon: "/brand/site-icon.png",
    shortcut: "/brand/site-icon.png",
    apple: "/brand/site-icon.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
