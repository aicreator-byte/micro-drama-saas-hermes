import { Suspense } from 'react';
import TimelinePage from './Client';

export const instant = false;

export default function Page() {
  return (
    <Suspense fallback={<p className="text-sm text-gray-500">Memuat…</p>}>
      <TimelinePage />
    </Suspense>
  );
}
