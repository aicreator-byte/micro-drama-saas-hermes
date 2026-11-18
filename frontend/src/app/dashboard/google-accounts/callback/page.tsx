'use client';

import { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { api } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/Card';
import { Loader2, CheckCircle, AlertCircle } from 'lucide-react';

/**
 * Google OAuth callback landing page. Google redirects here with
 * ?code=...&state=... after the user consents. The account id was saved
 * to sessionStorage by the "Connect via Google" button before redirect.
 */
function CallbackHandler() {
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<'working' | 'success' | 'error'>('working');
  const [message, setMessage] = useState('Exchanging authorization code...');

  useEffect(() => {
    const code = searchParams.get('code');
    const state = searchParams.get('state');
    const error = searchParams.get('error');
    if (error) {
      setStatus('error');
      setMessage(`Google refused authorization: ${error}`);
      return;
    }
    const accountId = sessionStorage.getItem('google_oauth_account_id');
    if (!code || !state || !accountId) {
      setStatus('error');
      setMessage('Missing authorization code, state, or account. Start the flow again from Google Accounts.');
      return;
    }
    sessionStorage.removeItem('google_oauth_account_id');
    api.googleOAuthCallback(code, state, accountId)
      .then(() => {
        setStatus('success');
        setMessage('Google account connected successfully.');
      })
      .catch((err: any) => {
        setStatus('error');
        setMessage(err.response?.data?.detail || 'OAuth callback failed.');
      });
  }, [searchParams]);

  return (
    <div className="flex items-center justify-center py-16">
      <Card className="w-full max-w-md">
        <CardContent className="p-8 text-center space-y-4">
          {status === 'working' && (
            <>
              <Loader2 className="w-10 h-10 animate-spin text-blue-600 mx-auto" aria-hidden="true" />
              <h1 className="text-xl font-semibold text-gray-900">Connecting Google account…</h1>
            </>
          )}
          {status === 'success' && (
            <>
              <CheckCircle className="w-10 h-10 text-green-600 mx-auto" aria-hidden="true" />
              <h1 className="text-xl font-semibold text-gray-900">Connected</h1>
            </>
          )}
          {status === 'error' && (
            <>
              <AlertCircle className="w-10 h-10 text-red-600 mx-auto" aria-hidden="true" />
              <h1 className="text-xl font-semibold text-gray-900">Connection failed</h1>
            </>
          )}
          <p className="text-sm text-gray-600">{message}</p>
          {status !== 'working' && (
            <Link href="/dashboard/google-accounts" className="inline-block text-sm font-medium text-blue-600 hover:underline">
              Back to Google Accounts
            </Link>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function GoogleOAuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-10 h-10 animate-spin text-blue-600" aria-hidden="true" />
        </div>
      }
    >
      <CallbackHandler />
    </Suspense>
  );
}
