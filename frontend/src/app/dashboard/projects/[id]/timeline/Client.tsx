'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { api } from '@/lib/api';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import type { Episode, VideoTimeline, TimelineClip } from '@/types';

export default function TimelinePage() {
  const params = useParams();
  const projectId = String(params.id);
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [episodeId, setEpisodeId] = useState('');
  const [timeline, setTimeline] = useState<VideoTimeline | null>(null);
  const [error, setError] = useState('');
  const [newLabel, setNewLabel] = useState('');
  const [newDuration, setNewDuration] = useState(8);

  useEffect(() => {
    api.listEpisodes(projectId, 1, 50).then((r) => {
      setEpisodes(r.items);
      if (r.items.length > 0) setEpisodeId(r.items[0].id);
    }).catch(console.error);
  }, [projectId]);

  useEffect(() => {
    if (!episodeId) return;
    setTimeline(null);
    setError('');
    api.getTimeline(projectId, episodeId).then(setTimeline).catch(() => setTimeline(null));
  }, [projectId, episodeId]);

  const createFromPrompts = async () => {
    setError('');
    try {
      const tl = await api.timelineFromPrompts(projectId, episodeId);
      setTimeline(tl);
    } catch (e) {
      setError('Episode ini belum punya prompt video-generation, atau timeline sudah ada.');
      console.error(e);
    }
  };

  const createEmpty = async () => {
    try {
      setTimeline(await api.createTimeline(projectId, episodeId, { name: 'Main timeline', clips: [] }));
    } catch (e) {
      setError('Gagal membuat timeline.');
      console.error(e);
    }
  };

  const saveClips = async (clips: TimelineClip[]) => {
    if (!timeline) return;
    const updated = await api.updateTimeline(projectId, episodeId, { clips });
    setTimeline(updated);
  };

  const addClip = async () => {
    if (!timeline) return;
    const start = timeline.duration_seconds;
    const clip: TimelineClip = {
      id: `clip-${Date.now()}`,
      track: 0,
      start,
      duration: newDuration,
      label: newLabel || `Shot ${timeline.clips.length + 1}`,
      transition: 'cut',
    };
    await saveClips([...timeline.clips, clip]);
    setNewLabel('');
  };

  const removeClip = async (id: string) => {
    if (!timeline) return;
    await saveClips(timeline.clips.filter((c) => c.id !== id));
  };

  const selected = episodes.find((e) => e.id === episodeId);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Timeline Video</h1>
      {error && <p className="text-red-600 text-sm">{error}</p>}
      <Card>
        <CardHeader><CardTitle>Pilih episode</CardTitle></CardHeader>
        <CardContent>
          <div className="flex gap-2 flex-wrap">
            {episodes.map((ep) => (
              <Button
                key={ep.id}
                size="sm"
                variant={ep.id === episodeId ? 'primary' : 'outline'}
                onClick={() => setEpisodeId(ep.id)}
              >
                EP{ep.episode_number} — {ep.title || 'tanpa judul'}
              </Button>
            ))}
            {episodes.length === 0 && <p className="text-sm text-gray-500">Belum ada episode di proyek ini.</p>}
          </div>
        </CardContent>
      </Card>
      {selected && !timeline && (
        <Card>
          <CardContent>
            <p className="text-sm text-gray-600 mb-3">Episode ini belum punya timeline.</p>
            <div className="flex gap-2">
              <Button onClick={createFromPrompts}>Bangun dari prompt video (8 dtk/shot)</Button>
              <Button variant="outline" onClick={createEmpty}>Buat timeline kosong</Button>
            </div>
          </CardContent>
        </Card>
      )}
      {timeline && (
        <Card>
          <CardHeader>
            <CardTitle>{timeline.name} — {timeline.duration_seconds} dtk, {timeline.fps} fps, {timeline.resolution}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {timeline.clips.length === 0 && <p className="text-sm text-gray-500">Belum ada clip.</p>}
              {[...timeline.clips].sort((a, b) => a.start - b.start).map((clip) => (
                <div key={clip.id} className="flex items-center gap-3 border rounded-lg px-3 py-2">
                  <Badge>track {clip.track}</Badge>
                  <span className="text-sm font-medium flex-1">{clip.label || clip.id}</span>
                  <span className="text-sm text-gray-500">{clip.start}s + {clip.duration}s</span>
                  {clip.transition && <span className="text-xs text-gray-400">{clip.transition}</span>}
                  <Button variant="ghost" size="sm" onClick={() => removeClip(clip.id)}>Hapus</Button>
                </div>
              ))}
            </div>
            <div className="flex gap-2 mt-4">
              <Input placeholder="Label clip baru" value={newLabel} onChange={(e) => setNewLabel(e.target.value)} />
              <Input
                type="number" min={1} max={60} value={newDuration}
                onChange={(e) => setNewDuration(Number(e.target.value) || 8)}
                className="w-24"
              />
              <Button onClick={addClip}>+ Tambah clip</Button>
              <Button variant="outline" onClick={async () => { await api.deleteTimeline(projectId, episodeId); setTimeline(null); }}>
                Hapus timeline
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
