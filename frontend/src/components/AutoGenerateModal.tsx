'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';
import { useProjectStore } from '@/lib/project-store';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { cn } from '@/lib/utils';
import type { Project, AutoGenerateJob, AutoGenerateJobStatus, AutoGenerateStep } from '@/types';
import {
  Sparkles,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  RotateCcw,
  ArrowRight,
} from 'lucide-react';

const STEP_LABELS: Record<string, string> = {
  series_bible: 'Series Bible',
  characters: 'Characters',
  locations: 'Locations',
  episodes: 'Episodes',
  prompts: 'Prompts',
};

const STEP_ORDER = ['series_bible', 'characters', 'locations', 'episodes', 'prompts'];

const RESULT_LINKS = [
  { label: 'Series Bible', href: '/dashboard/series-bible' },
  { label: 'Characters', href: '/dashboard/characters' },
  { label: 'Locations', href: '/dashboard/locations' },
  { label: 'Episodes', href: '/dashboard/episodes' },
  { label: 'Prompts', href: '/dashboard/prompts' },
];

function isTerminal(status: AutoGenerateJobStatus): boolean {
  return status === 'completed' || status === 'failed';
}

function extractErrorMessage(err: unknown): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const data = (err as { response?: { data?: { detail?: unknown } } }).response?.data;
    const detail = data?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail.map((d) => (typeof d === 'string' ? d : d?.msg ?? JSON.stringify(d))).join('; ');
    }
  }
  if (err instanceof Error) return err.message;
  return 'Request failed';
}

function summarizeStep(step: AutoGenerateStep): string | null {
  const summary = step.result_summary;
  if (!summary) return null;
  const parts = Object.entries(summary)
    .filter(([, v]) => typeof v === 'number' || typeof v === 'string')
    .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`);
  return parts.length > 0 ? parts.join(' · ') : null;
}

interface AutoGenerateModalProps {
  isOpen: boolean;
  onClose: () => void;
  project: Project | null;
  /** Called when the modal closes after a completed job (parent can refresh the list). */
  onCompleted?: () => void;
}

export function AutoGenerateModal({ isOpen, onClose, project, onCompleted }: AutoGenerateModalProps) {
  const [formTitle, setFormTitle] = useState('');
  const [formGenre, setFormGenre] = useState('');
  const [formNumEpisodes, setFormNumEpisodes] = useState(30);
  const [formPremise, setFormPremise] = useState('');
  const [job, setJob] = useState<AutoGenerateJob | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [retryingStep, setRetryingStep] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Reset form + job when the modal opens (new open session). Adjusted during
  // render — the documented React pattern for "state derived from props" —
  // instead of setState inside an effect (banned by react-hooks/set-state-in-effect).
  const [prevOpenKey, setPrevOpenKey] = useState<string | null>(null);
  const openKey = isOpen && project ? project.id : null;
  if (openKey !== prevOpenKey) {
    setPrevOpenKey(openKey);
    if (openKey && project) {
      setFormTitle(project.title);
      setFormGenre(project.genre ?? '');
      setFormNumEpisodes(30);
      setFormPremise('');
      setJob(null);
      setSubmitting(false);
      setRetryingStep(null);
      setError(null);
    }
  }

  // Poll job status while it is not terminal (backend runs sync, so this is
  // normally a no-op — it only matters if the server ever returns early).
  useEffect(() => {
    if (!job || !project || isTerminal(job.status)) return;
    const timer = setInterval(async () => {
      try {
        const fresh = await api.getAutoGenerateJob(project.id, job.id);
        setJob(fresh);
      } catch {
        // Keep last known state; next tick retries.
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [job, project]);

  const isRunning = submitting || retryingStep !== null || (job !== null && !isTerminal(job.status));

  const handleClose = () => {
    // Don't lose the job view while it is still running.
    if (isRunning) return;
    if (job?.status === 'completed') onCompleted?.();
    onClose();
  };

  const handleStart = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!project) return;
    const title = formTitle.trim();
    if (!title) {
      setError('Judul wajib diisi');
      return;
    }
    const numEpisodes = Math.min(50, Math.max(1, Number(formNumEpisodes) || 30));
    setSubmitting(true);
    setError(null);
    setJob(null);
    try {
      const created = await api.createAutoGenerateJob(project.id, {
        title,
        genre: formGenre.trim() || undefined,
        num_episodes: numEpisodes,
        premise: formPremise.trim() || undefined,
      });
      setJob(created);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  const handleRetry = async (stepKey: string) => {
    if (!project || !job) return;
    setRetryingStep(stepKey);
    setError(null);
    try {
      const updated = await api.retryAutoGenerateStep(project.id, job.id, stepKey);
      setJob(updated);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setRetryingStep(null);
    }
  };

  const openResults = () => {
    if (project) useProjectStore.getState().setCurrentProject(project);
  };

  const sortedSteps = job ? [...job.steps].sort((a, b) => a.step_order - b.step_order) : [];

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Auto-Generate"
      description={
        project
          ? `AI mengisi Series Bible, Characters, Locations, Episodes, dan Prompts untuk "${project.title}" secara berurutan. Video tidak dibuat otomatis — prompt dipakai manual di Google Flow.`
          : undefined
      }
      size="lg"
      closeOnOverlayClick={!isRunning}
      closeOnEscape={!isRunning}
    >
      {!job && !submitting ? (
        <form onSubmit={handleStart} className="space-y-4">
          <Input
            label="Judul"
            placeholder="My Amazing Micro Drama"
            value={formTitle}
            onChange={(e) => setFormTitle(e.target.value)}
            required
          />
          <Input
            label="Genre"
            placeholder="Drama, Romance, Thriller..."
            value={formGenre}
            onChange={(e) => setFormGenre(e.target.value)}
          />
          <Input
            label="Jumlah episode"
            type="number"
            min={1}
            max={50}
            value={formNumEpisodes}
            onChange={(e) => setFormNumEpisodes(Number(e.target.value))}
            helperText="1–50 episode (default 30)"
          />
          <Textarea
            label="Premis (opsional)"
            placeholder="Contoh: CEO kaya menyamar jadi OB untuk menguji calon istrinya..."
            value={formPremise}
            onChange={(e) => setFormPremise(e.target.value)}
            rows={3}
          />
          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</p>
          )}
          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit">
              <Sparkles className="w-4 h-4 mr-2" aria-hidden="true" />
              Start Auto-Generate
            </Button>
          </div>
        </form>
      ) : (
        <div className="space-y-4">
          {submitting && !job && (
            <div className="flex items-center gap-3 text-sm text-gray-600 bg-purple-50 border border-purple-200 rounded-lg px-3 py-2">
              <Loader2 className="w-4 h-4 animate-spin text-purple-600" aria-hidden="true" />
              Membuat job dan menjalankan 5 langkah… ini bisa memakan waktu beberapa menit.
            </div>
          )}

          {job && (
            <>
              <div
                className={cn(
                  'text-sm rounded-lg px-3 py-2 border',
                  job.status === 'completed' && 'bg-green-50 border-green-200 text-green-800',
                  job.status === 'failed' && 'bg-red-50 border-red-200 text-red-800',
                  !isTerminal(job.status) && 'bg-purple-50 border-purple-200 text-purple-800'
                )}
              >
                {job.status === 'completed' && 'Selesai — semua langkah berhasil. Hasil sudah tersimpan, bisa langsung dilihat di bawah.'}
                {job.status === 'failed' && `Job gagal${job.error_message ? `: ${job.error_message}` : '.'} Retry langkah yang gagal di bawah.`}
                {!isTerminal(job.status) && 'Job sedang berjalan…'}
              </div>

              <ul className="space-y-2">
                {STEP_ORDER.map((key) => {
                  const step = sortedSteps.find((s) => s.step_key === key);
                  const status = step?.status ?? 'pending';
                  const summary = step ? summarizeStep(step) : null;
                  return (
                    <li
                      key={key}
                      className="flex items-start gap-3 border border-gray-200 rounded-lg px-3 py-2.5"
                    >
                      <span className="mt-0.5 flex-shrink-0">
                        {status === 'completed' && <CheckCircle2 className="w-5 h-5 text-green-600" aria-hidden="true" />}
                        {status === 'failed' && <XCircle className="w-5 h-5 text-red-600" aria-hidden="true" />}
                        {status === 'running' && <Loader2 className="w-5 h-5 animate-spin text-purple-600" aria-hidden="true" />}
                        {status === 'pending' && <Clock className="w-5 h-5 text-gray-400" aria-hidden="true" />}
                        {status === 'skipped' && <CheckCircle2 className="w-5 h-5 text-gray-400" aria-hidden="true" />}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-gray-900">{STEP_LABELS[key]}</span>
                          <span
                            className={cn(
                              'text-xs px-2 py-0.5 rounded-full',
                              status === 'completed' && 'bg-green-100 text-green-800',
                              status === 'failed' && 'bg-red-100 text-red-800',
                              status === 'running' && 'bg-purple-100 text-purple-800',
                              status === 'pending' && 'bg-gray-100 text-gray-600',
                              status === 'skipped' && 'bg-gray-100 text-gray-600'
                            )}
                          >
                            {status}
                          </span>
                        </div>
                        {summary && <p className="mt-0.5 text-xs text-gray-500">{summary}</p>}
                        {step?.error_message && (
                          <p className="mt-0.5 text-xs text-red-600">{step.error_message}</p>
                        )}
                      </div>
                      {status === 'failed' && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleRetry(key)}
                          loading={retryingStep === key}
                          disabled={retryingStep !== null}
                        >
                          <RotateCcw className="w-3.5 h-3.5 mr-1" aria-hidden="true" />
                          Retry
                        </Button>
                      )}
                    </li>
                  );
                })}
              </ul>

              {job.status === 'completed' && (
                <div>
                  <p className="text-sm font-medium text-gray-900 mb-2">Lihat hasil:</p>
                  <div className="flex flex-wrap gap-2">
                    {RESULT_LINKS.map((link) => (
                      <Link key={link.href} href={link.href} onClick={openResults}>
                        <Button size="sm" variant="outline">
                          {link.label}
                          <ArrowRight className="w-3.5 h-3.5 ml-1" aria-hidden="true" />
                        </Button>
                      </Link>
                    ))}
                  </div>
                </div>
              )}

              {error && (
                <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</p>
              )}

              <div className="flex justify-end gap-3 pt-2">
                <Button variant="outline" onClick={handleClose} disabled={isRunning}>
                  {job.status === 'completed' ? 'Done' : 'Close'}
                </Button>
              </div>
              {isRunning && (
                <p className="text-xs text-gray-500 text-right">
                  Tunggu sampai job selesai atau gagal sebelum menutup — menutup sekarang akan kehilangan tampilan progres ini.
                </p>
              )}
            </>
          )}
        </div>
      )}
    </Modal>
  );
}
