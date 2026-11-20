'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { api } from '@/lib/api';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import type { SubtitleJob } from '@/types';

export default function SubtitlesPage() {
  const params = useParams();
  const projectId = String(params.id);
  const [jobs, setJobs] = useState<SubtitleJob[]>([]);
  const [engine, setEngine] = useState<{ available: boolean; engine: string | null; note: string | null }>({ available: false, engine: null, note: null });
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [segText, setSegText] = useState('0.0-2.0 Halo, saya Nadia.\n2.5-4.0 Selamat datang di episode ini.');

  const load = () => {
    api.listSubtitleJobs(projectId).then(setJobs).catch(console.error);
    api.getSubtitleEngine().then(setEngine).catch(console.error);
  };
  useEffect(load, [projectId]);

  const upload = async () => {
    if (!file) return;
    setUploading(true);
    setError('');
    try {
      await api.uploadSubtitleAudio(projectId, file);
      await load();
    } catch (e) {
      setError('Upload/transkrip gagal — cek format file & engine Whisper.');
      console.error(e);
    } finally {
      setUploading(false);
    }
  };

  const fromSegments = async () => {
    setError('');
    try {
      const segments = segText.split('\n').map((line) => {
        const m = line.match(/^([\d.]+)-([\d.]+)\s+(.+)$/);
        if (!m) throw new Error(`Baris tidak valid: ${line}`);
        return { start: Number(m[1]), end: Number(m[2]), text: m[3] };
      });
      await api.createSubtitleFromSegments(projectId, { segments });
      await load();
    } catch (e) {
      setError('Format segmen salah — pakai: start-end teks (satu baris per segmen).');
      console.error(e);
    }
  };

  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Subtitle Otomatis (Whisper)</h1>
      <Card>
        <CardHeader><CardTitle>Engine</CardTitle></CardHeader>
        <CardContent>
          {engine.available ? (
            <p className="text-sm">Whisper lokal aktif (<Badge>{engine.engine}</Badge>) — transkrip jalan di server, tanpa API key.</p>
          ) : (
            <p className="text-sm text-red-600">{engine.note || 'Engine Whisper belum tersedia di server.'}</p>
          )}
        </CardContent>
      </Card>
      {error && <p className="text-red-600 text-sm">{error}</p>}
      <Card>
        <CardHeader><CardTitle>Upload audio/video untuk ditranskrip</CardTitle></CardHeader>
        <CardContent>
          <div className="flex gap-2 items-center flex-wrap">
            <Input type="file" accept=".mp3,.wav,.m4a,.ogg,.flac,.mp4,.mov,.mkv,.webm" onChange={(e) => setFile(e.target.files?.[0] || null)} />
            <Button onClick={upload} disabled={!file || uploading} loading={uploading}>Transkrip</Button>
          </div>
          <p className="text-xs text-gray-500 mt-2">Maks 200 MB. Job jalan di background — refresh daftar untuk melihat status.</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Atau buat SRT/VTT dari segmen transkrip</CardTitle></CardHeader>
        <CardContent>
          <textarea
            className="w-full border rounded-lg p-2 text-sm font-mono"
            rows={4}
            value={segText}
            onChange={(e) => setSegText(e.target.value)}
          />
          <Button className="mt-2" onClick={fromSegments}>Buat SRT + VTT</Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Job subtitle</CardTitle></CardHeader>
        <CardContent>
          {jobs.length === 0 && <p className="text-sm text-gray-500">Belum ada job.</p>}
          <ul className="space-y-2">
            {jobs.map((job) => (
              <li key={job.id} className="flex items-center gap-3 border rounded-lg px-3 py-2 flex-wrap">
                <Badge>{job.status}</Badge>
                <span className="text-sm flex-1">{job.source_filename || 'dari segmen'} — {job.language} — {job.engine || '-'}</span>
                {job.segments && <span className="text-sm text-gray-500">{job.segments.length} segmen</span>}
                {job.status === 'completed' && (
                  <>
                    <a className="text-sm text-purple-600 underline" href={`${apiBase}/projects/${projectId}/subtitles/${job.id}/download?fmt=srt`}>SRT</a>
                    <a className="text-sm text-purple-600 underline" href={`${apiBase}/projects/${projectId}/subtitles/${job.id}/download?fmt=vtt`}>VTT</a>
                  </>
                )}
                {job.error_message && <span className="text-xs text-red-600">{job.error_message}</span>}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
