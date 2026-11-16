import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' });

export const metadata: Metadata = {
  title: 'Micro Drama SaaS - AI-Powered Drama Production Platform',
  description: 'Create short drama series from concept to final video with AI-powered tools',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} antialiased`}>
      <body className="bg-gray-50 text-gray-900">{children}</body>
    </html>
  );
}