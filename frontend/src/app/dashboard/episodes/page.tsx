'use client';

import { useEffect, useState } from 'react';
import { useProjectStore } from '@/lib/project-store';
import { api } from '@/lib/api';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { Select } from '@/components/ui/Select';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { formatDate, getStatusColor } from '@/lib/utils';
import { Plus, Edit, Save, Trash2, Film, Loader2, Sparkles } from 'lucide-react';

export default function EpisodesPage() {
  const { currentProject, episodes, fetchEpisodes, createEpisode, updateEpisode, deleteEpisode } = useProjectStore();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingEpisode, setEditingEpisode] = useState<typeof episodes[0] | null>(null);
  const [generatingEpisode, setGeneratingEpisode] = useState<typeof episodes[0] | null>(null);
  const [formData, setFormData] = useState({
    episode_number: (episodes.length + 1).toString(),
    title: '',
    outline: '',
    production_notes: '',
    estimated_cost: '',
  });
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [generateForm, setGenerateForm] = useState({
    premise: '',
    genre: 'drama',
    num_episodes: '20',
    tone: '',
  });

  useEffect(() => {
    if (currentProject) {
      fetchEpisodes(currentProject.id);
    }
  }, [currentProject, fetchEpisodes]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentProject) return;
    setSaving(true);
    try {
      await createEpisode(currentProject.id, {
        title: formData.title,
        outline: formData.outline,
        production_notes: formData.production_notes,
        episode_number: parseInt(formData.episode_number) || (episodes.length + 1),
        estimated_cost: formData.estimated_cost ? parseFloat(formData.estimated_cost) : undefined,
      });
      setShowCreateModal(false);
      resetForm();
    } catch (error) {
      console.error('Failed to create episode:', error);
      alert('Failed to create episode');
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentProject || !editingEpisode) return;
    setSaving(true);
    try {
      await updateEpisode(currentProject.id, editingEpisode.id, {
        title: formData.title,
        outline: formData.outline,
        production_notes: formData.production_notes,
        episode_number: parseInt(formData.episode_number) || editingEpisode.episode_number,
        estimated_cost: formData.estimated_cost ? parseFloat(formData.estimated_cost) : undefined,
      });
      setEditingEpisode(null);
      resetForm();
    } catch (error) {
      console.error('Failed to update episode:', error);
      alert('Failed to update episode');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (episodeId: string) => {
    if (!currentProject) return;
    if (!confirm('Are you sure you want to delete this episode?')) return;
    setDeletingId(episodeId);
    try {
      await deleteEpisode(currentProject.id, episodeId);
    } catch (error) {
      console.error('Failed to delete episode:', error);
      alert('Failed to delete episode');
    } finally {
      setDeletingId(null);
    }
  };

  const startEdit = (episode: typeof episodes[0]) => {
    setEditingEpisode(episode);
    setFormData({
      episode_number: episode.episode_number.toString(),
      title: episode.title || '',
      outline: episode.outline || '',
      production_notes: episode.production_notes || '',
      estimated_cost: episode.estimated_cost?.toString() || '',
    });
  };

  const resetForm = () => {
    setFormData({
      episode_number: (episodes.length + 1).toString(),
      title: '',
      outline: '',
      production_notes: '',
      estimated_cost: '',
    });
  };

  const handleGenerateSeries = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentProject || !generateForm.premise.trim()) return;
    setGenerating(true);
    try {
      await useProjectStore.getState().generateSeries(currentProject.id, {
        premise: generateForm.premise.trim(),
        genre: generateForm.genre || undefined,
        num_episodes: parseInt(generateForm.num_episodes) || 20,
        tone: generateForm.tone || undefined,
      });
      setShowGenerateModal(false);
    } catch (error) {
      console.error('Failed to generate series:', error);
      alert('Failed to generate series');
    } finally {
      setGenerating(false);
    }
  };

  const handleGenerateScenes = async (episode: typeof episodes[0]) => {
    if (!currentProject) return;
    setGeneratingEpisode(episode);
    setGenerating(true);
    try {
      // Get characters and locations for context
      const chars = await api.listCharacters(currentProject.id);
      const locs = await api.listLocations(currentProject.id);
      
      await useProjectStore.getState().breakdownEpisode(currentProject.id, episode.id, {
        episode_outline: episode.outline || '',
        characters: chars.items.map((c: { id: string; name: string; role: string | null }) => ({ id: c.id, name: c.name, role: c.role })),
        locations: locs.items.map((l: { id: string; name: string }) => ({ id: l.id, name: l.name })),
      });
      
      // Update episode status
      await updateEpisode(currentProject.id, episode.id, { status: 'scenes_ready' });
      alert('Scenes generated successfully!');
    } catch (error) {
      console.error('Failed to generate scenes:', error);
      alert('Failed to generate scenes');
    } finally {
      setGeneratingEpisode(null);
      setGenerating(false);
    }
  };

  if (!currentProject) {
    return (
      <div className="text-center py-16">
        <Film className="w-16 h-16 text-gray-300 mx-auto mb-4" aria-hidden="true" />
        <h2 className="text-xl font-semibold text-gray-900 mb-2">No project selected</h2>
        <p className="text-gray-500 mb-4">Select a project from the dashboard to manage episodes</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Episodes</h1>
          <p className="text-gray-600">Manage your episode outlines and production status</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => { resetForm(); setShowCreateModal(true); }}>
            <Plus className="w-4 h-4 mr-2" aria-hidden="true" />
            Add Episode
          </Button>
          <Button onClick={() => setShowGenerateModal(true)}>
            <Sparkles className="w-4 h-4 mr-2" aria-hidden="true" />
            Generate Series
          </Button>
        </div>
      </div>

      {episodes.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center">
            <Film className="w-16 h-16 text-gray-300 mx-auto mb-4" aria-hidden="true" />
            <h3 className="text-lg font-medium text-gray-900 mb-1">No episodes yet</h3>
            <p className="text-gray-500 mb-4">Create episodes or generate a full series from your premise</p>
            <div className="flex gap-2 justify-center">
              <Button onClick={() => { resetForm(); setShowCreateModal(true); }}>
                <Plus className="w-4 h-4 mr-2" aria-hidden="true" />
                Add Episode
              </Button>
              <Button variant="outline" onClick={() => setShowGenerateModal(true)}>
                <Sparkles className="w-4 h-4 mr-2" aria-hidden="true" />
                Generate Series
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {episodes.map((episode) => (
            <Card key={episode.id} className="group">
              <CardContent className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="w-8 h-8 bg-purple-100 rounded-full flex items-center justify-center text-purple-600 font-semibold text-sm">
                        {episode.episode_number}
                      </span>
                      <h3 className="font-semibold text-gray-900">{episode.title || `Episode ${episode.episode_number}`}</h3>
                      <Badge className={getStatusColor(episode.status)}>
                        {episode.status.replace('_', ' ')}
                      </Badge>
                    </div>
                    <p className="mt-1 text-sm text-gray-500 line-clamp-2">
                      {episode.outline || 'No outline'}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-gray-500">
                      {episode.estimated_cost && <span>Est. Cost: ${episode.estimated_cost.toLocaleString()}</span>}
                      {episode.actual_cost && <span>Actual: ${episode.actual_cost.toLocaleString()}</span>}
                      <span>Updated {formatDate(episode.updated_at)}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 ml-4">
                    <button
                      onClick={() => startEdit(episode)}
                      className="p-2 text-gray-400 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                      aria-label="Edit episode"
                    >
                      <Edit className="w-4 h-4" aria-hidden="true" />
                    </button>
                    {episode.status === 'planned' || episode.status === 'writing' ? (
                      <button
                        onClick={() => handleGenerateScenes(episode)}
                        disabled={generatingEpisode?.id === episode.id}
                        className="p-2 text-gray-400 hover:text-green-600 hover:bg-green-50 rounded-lg transition-colors disabled:opacity-50"
                        aria-label="Generate scenes"
                      >
                        {generatingEpisode?.id === episode.id ? (
                          <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
                        ) : (
                          <Sparkles className="w-4 h-4" aria-hidden="true" />
                        )}
                      </button>
                    ) : null}
                    <button
                      onClick={() => handleDelete(episode.id)}
                      disabled={deletingId === episode.id}
                      className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50"
                      aria-label="Delete episode"
                    >
                      {deletingId === episode.id ? (
                        <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
                      ) : (
                        <Trash2 className="w-4 h-4" aria-hidden="true" />
                      )}
                    </button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Generate Series Modal */}
      <Modal
        isOpen={showGenerateModal}
        onClose={() => setShowGenerateModal(false)}
        title="Generate Series"
      >
        <form onSubmit={handleGenerateSeries} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Premise *</label>
            <Textarea
              value={generateForm.premise}
              onChange={(e) => setGenerateForm({ ...generateForm, premise: e.target.value })}
              placeholder="e.g., A poor seamstress inherits a fashion empire and must outwit the family that humiliated her."
              rows={4}
              required
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Genre</label>
              <Input
                value={generateForm.genre}
                onChange={(e) => setGenerateForm({ ...generateForm, genre: e.target.value })}
                placeholder="drama"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Episodes</label>
              <Input
                type="number"
                min="1"
                max="50"
                value={generateForm.num_episodes}
                onChange={(e) => setGenerateForm({ ...generateForm, num_episodes: e.target.value })}
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Tone</label>
            <Input
              value={generateForm.tone}
              onChange={(e) => setGenerateForm({ ...generateForm, tone: e.target.value })}
              placeholder="e.g., dramatic, romantic, tense"
            />
          </div>
          <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-2">
            Regenerating replaces existing episodes. The current episodes are snapshotted as revisions first.
          </p>
          <div className="flex gap-2 justify-end">
            <Button type="button" variant="outline" onClick={() => setShowGenerateModal(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={generating || !generateForm.premise.trim()}>
              <Sparkles className="w-4 h-4 mr-2" aria-hidden="true" />
              {generating ? 'Generating...' : 'Generate Series'}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Create/Edit Modal */}
      <Modal
        isOpen={showCreateModal || !!editingEpisode}
        onClose={() => { setShowCreateModal(false); setEditingEpisode(null); resetForm(); }}
        title={editingEpisode ? 'Edit Episode' : 'Create Episode'}
        size="lg"
      >
        <form onSubmit={editingEpisode ? handleUpdate : handleCreate} className="space-y-4 max-h-[80vh] overflow-y-auto pr-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Input
              label="Episode Number"
              type="number"
              min="1"
              value={formData.episode_number}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, episode_number: e.target.value })}
              required
            />
            <Input
              label="Title"
              placeholder="Episode title"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
            />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Input
              label="Estimated Cost"
              type="number"
              placeholder="0.00"
              value={formData.estimated_cost}
              onChange={(e) => setFormData({ ...formData, estimated_cost: e.target.value })}
            />
          </div>
          <Textarea
            label="Outline"
            placeholder="Detailed episode outline..."
            value={formData.outline}
            onChange={(e) => setFormData({ ...formData, outline: e.target.value })}
            rows={4}
          />
          <Textarea
            label="Production Notes"
            placeholder="Notes for production team..."
            value={formData.production_notes}
            onChange={(e) => setFormData({ ...formData, production_notes: e.target.value })}
            rows={2}
          />
          <div className="flex justify-end gap-3 pt-4 border-t">
            <Button type="button" variant="outline" onClick={() => { setShowCreateModal(false); setEditingEpisode(null); resetForm(); }}>
              Cancel
            </Button>
            <Button type="submit" loading={saving}>
              <Loader2 className="w-4 h-4 mr-2" aria-hidden="true" />
              {editingEpisode ? 'Save Changes' : 'Create Episode'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}