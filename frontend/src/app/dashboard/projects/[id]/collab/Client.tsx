'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import { api } from '@/lib/api';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { Badge } from '@/components/ui/Badge';
import type { CollabPresence, Project, SeriesBible } from '@/types';

type WsMsg = {
  type: string;
  users?: CollabPresence[];
  resource?: string;
  field?: string;
  value?: string;
  by?: string;
  version?: number;
  detail?: string;
};

export default function CollabPage() {
  const params = useParams();
  const projectId = String(params.id);
  const [project, setProject] = useState<Project | null>(null);
  const [bible, setBible] = useState<SeriesBible | null>(null);
  const [presence, setPresence] = useState<CollabPresence[]>([]);
  const [connected, setConnected] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const [title, setTitle] = useState('');
  const [plot, setPlot] = useState('');
  const wsRef = useRef<WebSocket | null>(null);

  const pushLog = (line: string) => setLog((l) => [line, ...l].slice(0, 20));

  useEffect(() => {
    let alive = true;
    api.getProject(projectId).then((p) => {
      if (!alive) return;
      setProject(p);
      setTitle(p.title);
    }).catch(console.error);
    api.getSeriesBible(projectId).then((b) => {
      if (!alive) return;
      setBible(b);
      setPlot(b.main_plot || '');
    }).catch(() => setBible(null));
    api.getCollabPresence(projectId).then(setPresence).catch(console.error);

    const stored = typeof window !== 'undefined' ? localStorage.getItem('auth_tokens') : null;
    const token = stored ? JSON.parse(stored).access_token as string : '';
    const base = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1')
      .replace('/api/v1', '')
      .replace('http', 'ws');
    // JWT lewat subprotocol WS (audit ronde 2, P2-3) — bukan query param,
    // supaya token tidak masuk access log server.
    const ws = new WebSocket(`${base}/api/v1/projects/${projectId}/collab/ws`, ['collab', token]);
    wsRef.current = ws;
    ws.onopen = () => { setConnected(true); pushLog('Terhubung ke room kolaborasi.'); };
    ws.onclose = () => setConnected(false);
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data) as WsMsg;
      if (msg.type === 'presence' && msg.users) setPresence(msg.users);
      if (msg.type === 'update') {
        pushLog(`Update v${msg.version} dari ${msg.by}: ${msg.resource}.${msg.field}`);
        if (msg.resource === 'project' && msg.field === 'title' && msg.value) setTitle(msg.value);
        if (msg.resource === 'series_bible' && msg.field === 'main_plot' && msg.value) setPlot(msg.value);
      }
      if (msg.type === 'error') pushLog(`Error: ${msg.detail}`);
    };
    return () => { alive = false; ws.close(); };
  }, [projectId]);

  const sendEdit = (resource: string, resourceId: string, field: string, value: string) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'edit', resource, resource_id: resourceId, field, value }));
    } else {
      api.postCollabEdit(projectId, { resource, resource_id: resourceId, field, value })
        .then((r) => pushLog(`Edit tersimpan via REST (v${r.version}) — WS tidak terhubung.`))
        .catch((e) => pushLog(`Gagal menyimpan: ${e}`));
    }
  };

  const setEditingField = (field: string | null) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'presence', field }));
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold">Kolaborasi Real-time</h1>
        <Badge>{connected ? 'Terhubung (WS)' : 'Tidak terhubung'}</Badge>
      </div>
      <Card>
        <CardHeader><CardTitle>Yang sedang online</CardTitle></CardHeader>
        <CardContent>
          {presence.length === 0 ? (
            <p className="text-sm text-gray-500">Belum ada editor lain di proyek ini.</p>
          ) : (
            <ul className="space-y-1">
              {presence.map((p) => (
                <li key={p.user_id} className="text-sm">
                  <span className="inline-block w-3 h-3 rounded-full mr-2" style={{ background: p.color }} />
                  {p.name}
                  {p.field && <span className="text-gray-500"> — sedang edit {p.field}</span>}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Edit bersama — judul proyek</CardTitle></CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              onFocus={() => setEditingField('project.title')}
              onBlur={() => setEditingField(null)}
            />
            <Button onClick={() => project && sendEdit('project', project.id, 'title', title)}>
              Simpan &amp; siarkan
            </Button>
          </div>
        </CardContent>
      </Card>
      {bible && (
        <Card>
          <CardHeader><CardTitle>Edit bersama — plot utama bible</CardTitle></CardHeader>
          <CardContent>
            <Textarea
              value={plot}
              rows={5}
              onChange={(e) => setPlot(e.target.value)}
              onFocus={() => setEditingField('series_bible.main_plot')}
              onBlur={() => setEditingField(null)}
            />
            <Button className="mt-2" onClick={() => sendEdit('series_bible', bible.id, 'main_plot', plot)}>
              Simpan &amp; siarkan
            </Button>
          </CardContent>
        </Card>
      )}
      <Card>
        <CardHeader><CardTitle>Aktivitas</CardTitle></CardHeader>
        <CardContent>
          {log.length === 0 ? <p className="text-sm text-gray-500">Belum ada aktivitas.</p> : (
            <ul className="text-sm space-y-1">{log.map((l, i) => <li key={i}>{l}</li>)}</ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
