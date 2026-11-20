'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { api } from '@/lib/api';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import type { ConsistencyCheck } from '@/types';

const SEV_COLOR: Record<string, string> = { high: 'bg-red-100 text-red-800', medium: 'bg-yellow-100 text-yellow-800', low: 'bg-gray-100 text-gray-700' };

export default function ConsistencyPage() {
  const params = useParams();
  const projectId = String(params.id);
  const [checks, setChecks] = useState<ConsistencyCheck[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');

  const load = () => api.listConsistencyChecks(projectId).then(setChecks).catch(console.error);
  useEffect(() => { load(); }, [projectId]);

  const run = async () => {
    setRunning(true);
    setError('');
    try {
      // POST kembali langsung (201, status running) — cek jalan di
      // background (audit ronde 2, P1-1). Poll sampai selesai/gagal.
      const created = await api.runConsistencyCheck(projectId);
      let latest_status = created.status;
      for (let i = 0; i < 150 && latest_status === 'running'; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        const checks = await api.listConsistencyChecks(projectId);
        const cur = checks.find((c) => c.id === created.id);
        if (cur) latest_status = cur.status;
      }
      await load();
    } catch (e) {
      setError('Cek gagal — pastikan proyek sudah punya karakter.');
      console.error(e);
    } finally {
      setRunning(false);
    }
  };

  const latest = checks[0];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold">Cek Konsistensi Karakter (AI)</h1>
        <Button onClick={run} loading={running}>Jalankan cek</Button>
      </div>
      <p className="text-sm text-gray-500">
        Membandingkan bible karakter dengan outline tiap episode — rule-based + LLM.
        Bila LLM gagal, hasil rule-based tetap disimpan.
      </p>
      {error && <p className="text-red-600 text-sm">{error}</p>}
      {latest && (
        <Card>
          <CardHeader>
            <CardTitle>
              Cek terakhir — {new Date(latest.created_at).toLocaleString('id-ID')} — {latest.issue_count} masalah
            </CardTitle>
          </CardHeader>
          <CardContent>
            {latest.status === 'running' && <p className="text-sm text-blue-700">Cek sedang berjalan di background — halaman ini me-refresh otomatis.</p>}
            {latest.status === 'failed' && <p className="text-red-600 text-sm">{latest.error_message}</p>}
            {(!latest.issues || latest.issues.length === 0) && latest.status === 'completed' && (
              <p className="text-sm text-green-700">Tidak ada inkonsistensi terdeteksi.</p>
            )}
            <div className="space-y-3">
              {(latest.issues || []).map((issue, i) => (
                <div key={i} className="border rounded-lg p-3">
                  <div className="flex gap-2 items-center flex-wrap">
                    <span className={`text-xs px-2 py-0.5 rounded ${SEV_COLOR[issue.severity] || ''}`}>{issue.severity}</span>
                    <Badge>{issue.type}</Badge>
                    <span className="font-medium text-sm">{issue.character || '(umum)'}</span>
                    {issue.episode_number != null && <span className="text-sm text-gray-500">EP{issue.episode_number}</span>}
                  </div>
                  <p className="text-sm mt-1">{issue.description}</p>
                  {issue.suggestion && <p className="text-sm text-gray-500 mt-1">Saran: {issue.suggestion}</p>}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
      {checks.length > 1 && (
        <Card>
          <CardHeader><CardTitle>Riwayat cek</CardTitle></CardHeader>
          <CardContent>
            <ul className="text-sm space-y-1">
              {checks.slice(1).map((c) => (
                <li key={c.id}>
                  {new Date(c.created_at).toLocaleString('id-ID')} — {c.issue_count} masalah — {c.status}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
