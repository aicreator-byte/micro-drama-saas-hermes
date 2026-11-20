'use client';

import { ReactNode, Suspense } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';

export default function DashboardLayoutWrapper({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-gray-500">Memuat…</div>}>
      <DashboardLayout>{children}</DashboardLayout>
    </Suspense>
  );
}
