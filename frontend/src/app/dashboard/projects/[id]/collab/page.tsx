import { Suspense } from 'react';
import CollabPage from './Client';

export const instant = false;

export default function Page() {
  return (
    <Suspense fallback={<p className="text-sm text-gray-500">Memuat…</p>}>
      <CollabPage />
    </Suspense>
  );
}
