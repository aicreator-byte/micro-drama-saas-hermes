'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import type { BillingPlan, Subscription } from '@/types';

export default function BillingPage() {
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [sub, setSub] = useState<Subscription | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');

  const load = async () => {
    try {
      const [p, s] = await Promise.all([api.listBillingPlans(), api.getSubscription()]);
      setPlans(p);
      setSub(s);
    } catch (e) {
      setError('Gagal memuat billing.');
      console.error(e);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const checkout = async (planId: string) => {
    setBusy(planId);
    setError('');
    try {
      const res = await api.createCheckout(planId);
      if (res.checkout_url) window.open(res.checkout_url, '_blank');
      await load();
    } catch (e) {
      setError('Checkout gagal.');
      console.error(e);
    } finally {
      setBusy('');
    }
  };

  const cancel = async () => {
    if (!confirm('Batalkan langganan dan kembali ke Free?')) return;
    try {
      await api.cancelSubscription();
      await load();
    } catch (e) {
      setError('Gagal membatalkan.');
      console.error(e);
    }
  };

  const fmt = (n: number) => `Rp${n.toLocaleString('id-ID')}`;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Billing &amp; Langganan</h1>
        <p className="text-gray-500 text-sm mt-1">
          Mode TEST/SANDBOX — tidak ada pembayaran nyata, tidak ada kartu kredit.
          Checkout membuka URL simulasi.
        </p>
      </div>
      {error && <p className="text-red-600 text-sm">{error}</p>}
      {sub && (
        <Card>
          <CardHeader><CardTitle>Langganan saat ini</CardTitle></CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <Badge>{sub.plan}</Badge>
              <Badge>{sub.status}</Badge>
              <span className="text-sm text-gray-500">provider: {sub.provider} (test)</span>
              {sub.current_period_end && (
                <span className="text-sm text-gray-500">
                  berakhir: {new Date(sub.current_period_end).toLocaleDateString('id-ID')}
                </span>
              )}
              {sub.status === 'active' && sub.plan !== 'free' && (
                <Button variant="outline" size="sm" onClick={cancel}>Batalkan</Button>
              )}
            </div>
          </CardContent>
        </Card>
      )}
      <div className="grid md:grid-cols-3 gap-4">
        {plans.map((plan) => (
          <Card key={plan.id}>
            <CardHeader><CardTitle>{plan.name}</CardTitle></CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{plan.price_idr === 0 ? 'Gratis' : `${fmt(plan.price_idr)}/bln`}</p>
              <ul className="mt-3 space-y-1 text-sm text-gray-600">
                {plan.features.map((f) => <li key={f}>• {f}</li>)}
              </ul>
              <Button
                className="mt-4 w-full"
                variant={sub?.plan === plan.id ? 'secondary' : 'primary'}
                disabled={sub?.plan === plan.id || busy === plan.id}
                loading={busy === plan.id}
                onClick={() => checkout(plan.id)}
              >
                {sub?.plan === plan.id ? 'Paket aktif' : plan.price_idr === 0 ? 'Aktifkan Free' : `Pilih ${plan.name} (test)`}
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
