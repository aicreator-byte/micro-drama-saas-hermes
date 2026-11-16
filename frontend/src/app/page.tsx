'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/auth-store';
import { Clapperboard } from 'lucide-react';

export default function HomePage() {
  const router = useRouter();
  const { isAuthenticated, checkAuth } = useAuthStore();

  useEffect(() => {
    const initAuth = async () => {
      const authenticated = await checkAuth();
      if (authenticated) {
        router.push('/dashboard');
      } else {
        router.push('/auth/login');
      }
    };
    initAuth();
  }, [checkAuth, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-purple-50 via-white to-blue-50">
      <div className="text-center">
        <div className="w-16 h-16 bg-gradient-to-br from-purple-600 to-blue-600 rounded-xl flex items-center justify-center mx-auto mb-4">
          <Clapperboard className="w-8 h-8 text-white" />
        </div>
        <h1 className="text-2xl font-bold text-gray-900">Micro Drama SaaS</h1>
        <p className="mt-2 text-gray-600">Loading...</p>
      </div>
    </div>
  );
}