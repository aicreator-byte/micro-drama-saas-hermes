'use client';

import { useEffect, useState } from 'react';
import { useProjectStore } from '@/lib/project-store';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/Select';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { formatDate, cn } from '@/lib/utils';
import { Plus, Edit, Save, Trash2, Loader2, MessageSquare, Mic, Volume2, Copy } from 'lucide-react';

export default function DialoguesPage() {
  const { currentProject, scenes, characters, selectedScene, setSelectedScene, fetchDialogues, createDialogue, updateDialogue, deleteDialogue } = useProjectStore();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingDialogue, setEditingDialogue] = useState<{ id: string; scene_id: string; character_id: string; order_index: number; text: string; direction: string | null; audio_prompt: string | null } | null>(null);
  const [formData, setFormData] = useState({
    scene_id: '',
    character_id: '',
    order_index: 0,
    text: '',
    direction: '',
    audio_prompt: '',
  });
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Get episodeId from selected scene
  const selectedSceneObj = selectedScene ? Object.values(scenes).flat().find(s => s.id === selectedScene) : null;
  const episodeId = selectedSceneObj?.episode_id || '';

  useEffect(() => {
    if (currentProject && selectedScene && episodeId) {
      fetchDialogues(currentProject.id, episodeId, selectedScene);
    }
  }, [currentProject, selectedScene, episodeId, fetchDialogues]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentProject || !episodeId) return;
    setSaving(true);
    try {
      await createDialogue(currentProject.id, episodeId, formData.scene_id, {
        character_id: formData.character_id,
        order_index: formData.order_index,
        text: formData.text,
        direction: formData.direction || undefined,
        audio_prompt: formData.audio_prompt || undefined,
      });
      setShowCreateModal(false);
      resetForm();
    } catch (error) {
      console.error('Failed to create dialogue:', error);
      alert('Failed to create dialogue');
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentProject || !editingDialogue || !episodeId) return;
    setSaving(true);
    try {
      await updateDialogue(currentProject.id, episodeId, editingDialogue.scene_id, editingDialogue.id, {
        character_id: formData.character_id,
        order_index: formData.order_index,
        text: formData.text,
        direction: formData.direction || undefined,
        audio_prompt: formData.audio_prompt || undefined,
      });
      setEditingDialogue(null);
      resetForm();
    } catch (error) {
      console.error('Failed to update dialogue:', error);
      alert('Failed to update dialogue');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (sceneId: string, dialogueId: string) => {
    if (!currentProject || !episodeId) return;
    if (!confirm('Are you sure you want to delete this dialogue?')) return;
    setDeletingId(dialogueId);
    try {
      await deleteDialogue(currentProject.id, episodeId, sceneId, dialogueId);
    } catch (error) {
      console.error('Failed to delete dialogue:', error);
      alert('Failed to delete dialogue');
    } finally {
      setDeletingId(null);
    }
  };

  const startEdit = (dialogue: { id: string; scene_id: string; character_id: string; order_index: number; text: string; direction: string | null; audio_prompt: string | null; character?: { name: string } }) => {
    setEditingDialogue(dialogue);
    setFormData({
      scene_id: dialogue.scene_id,
      character_id: dialogue.character_id,
      order_index: dialogue.order_index,
      text: dialogue.text,
      direction: dialogue.direction || '',
      audio_prompt: dialogue.audio_prompt || '',
    });
  };

  const resetForm = () => {
    setFormData({
      scene_id: selectedScene || '',
      character_id: '',
      order_index: 0,
      text: '',
      direction: '',
      audio_prompt: '',
    });
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    alert('Copied to clipboard!');
  };

  if (!currentProject) {
    return (
      <div className="text-center py-16">
        <MessageSquare className="w-16 h-16 text-gray-300 mx-auto mb-4" aria-hidden="true" />
        <h2 className="text-xl font-semibold text-gray-900 mb-2">No project selected</h2>
        <p className="text-gray-500 mb-4">Select a project from the dashboard to manage dialogues</p>
      </div>
    );
  }

  const sceneDialogues = selectedScene ? (useProjectStore.getState().dialogues[selectedScene] || []) : [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dialogues</h1>
          <p className="text-gray-600">Write and manage dialogue lines for your scenes</p>
        </div>
        <div className="flex items-center gap-2">
          <Select
            value={selectedScene || ''}
            onValueChange={(v) => { setSelectedScene(v || null); resetForm(); }}
            placeholder="Select a scene first"
          >
            <SelectTrigger className="w-64">
              <SelectValue placeholder="Select scene..." />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">-- Select Scene --</SelectItem>
              {Object.values(scenes).flat().map(scene => (
                <SelectItem key={scene.id} value={scene.id}>
                  Ep {scene.episode_id?.slice(-4)} - Scene {scene.scene_number}: {scene.title || 'Untitled'}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button onClick={() => { resetForm(); setShowCreateModal(true); }} disabled={!selectedScene}>
            <Plus className="w-4 h-4 mr-2" aria-hidden="true" />
            Add Dialogue
          </Button>
        </div>
      </div>

      {!selectedScene ? (
        <Card>
          <CardContent className="py-16 text-center">
            <MessageSquare className="w-16 h-16 text-gray-300 mx-auto mb-4" aria-hidden="true" />
            <h3 className="text-lg font-medium text-gray-900 mb-1">Select a scene</h3>
            <p className="text-gray-500">Choose a scene from the dropdown to view and edit its dialogues</p>
          </CardContent>
        </Card>
      ) : sceneDialogues.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center">
            <MessageSquare className="w-16 h-16 text-gray-300 mx-auto mb-4" aria-hidden="true" />
            <h3 className="text-lg font-medium text-gray-900 mb-1">No dialogues yet</h3>
            <p className="text-gray-500 mb-4">Add dialogue lines for this scene</p>
            <Button onClick={() => { resetForm(); setShowCreateModal(true); }}>
              <Plus className="w-4 h-4 mr-2" aria-hidden="true" />
              Add Dialogue
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {sceneDialogues.map((dialogue) => (
            <Card
              key={dialogue.id}
              className={cn('group', editingDialogue?.id === dialogue.id && 'ring-2 ring-purple-500')}
            >
              <CardContent className="p-4">
                <div className="flex items-start gap-4">
                  <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center text-purple-600 flex-shrink-0">
                    <MessageSquare className="w-5 h-5" aria-hidden="true" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-500">#{dialogue.order_index + 1}</span>
                      {dialogue.character && (
                        <Badge variant="purple" className="text-xs">
                          {dialogue.character.name}
                        </Badge>
                      )}
                    </div>
                    <p className="mt-1 text-gray-900">{dialogue.text}</p>
                    {dialogue.direction && (
                      <p className="mt-1 text-sm text-gray-500 italic">Direction: {dialogue.direction}</p>
                    )}
                    {dialogue.audio_prompt && (
                      <p className="mt-1 text-sm text-gray-500">
                        <Mic className="w-3 h-3 inline mr-1" aria-hidden="true" />
                        Audio: {dialogue.audio_prompt.slice(0, 80)}...
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => copyToClipboard(dialogue.text)}
                      className="p-2 text-gray-400 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                      aria-label="Copy dialogue"
                    >
                      <Copy className="w-4 h-4" aria-hidden="true" />
                    </button>
                    {dialogue.audio_prompt && (
                      <button
                        className="p-2 text-gray-400 hover:text-green-600 hover:bg-green-50 rounded-lg transition-colors"
                        aria-label="Copy audio prompt"
                      >
                        <Volume2 className="w-4 h-4" aria-hidden="true" />
                      </button>
                    )}
                    <button
                      onClick={() => startEdit(dialogue)}
                      className="p-2 text-gray-400 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                      aria-label="Edit dialogue"
                    >
                      <Edit className="w-4 h-4" aria-hidden="true" />
                    </button>
                    <button
                      onClick={() => handleDelete(selectedScene, dialogue.id)}
                      disabled={deletingId === dialogue.id}
                      className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50"
                      aria-label="Delete dialogue"
                    >
                      {deletingId === dialogue.id ? (
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

      {/* Create/Edit Modal */}
      <Modal
        isOpen={showCreateModal || !!editingDialogue}
        onClose={() => { setShowCreateModal(false); setEditingDialogue(null); resetForm(); }}
        title={editingDialogue ? 'Edit Dialogue' : 'Add Dialogue'}
        size="lg"
      >
        <form onSubmit={editingDialogue ? handleUpdate : handleCreate} className="space-y-4 max-h-[80vh] overflow-y-auto pr-4">
          {!editingDialogue && (
            <Select
              value={formData.scene_id}
              onValueChange={(v) => setFormData({ ...formData, scene_id: v })}
              placeholder="Select scene"
            >
              <SelectTrigger>
                <SelectValue placeholder="Scene" />
              </SelectTrigger>
              <SelectContent>
                {Object.values(scenes).flat().map(scene => (
                  <SelectItem key={scene.id} value={scene.id}>
                    Ep {scene.episode_id?.slice(-4)} - Scene {scene.scene_number}: {scene.title || 'Untitled'}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          {editingDialogue && (
            <input type="hidden" value={editingDialogue.scene_id} />
          )}
          <Select
            value={formData.character_id}
            onValueChange={(v) => setFormData({ ...formData, character_id: v })}
            placeholder="Select character"
          >
            <SelectTrigger>
              <SelectValue placeholder="Character" />
            </SelectTrigger>
            <SelectContent>
              {characters.map(char => (
                <SelectItem key={char.id} value={char.id}>{char.name} ({char.role || 'No role'})</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="grid gap-4 md:grid-cols-2">
            <Input
              label="Order Index"
              type="number"
              min="0"
              value={formData.order_index}
              onChange={(e) => setFormData({ ...formData, order_index: parseInt(e.target.value) || 0 })}
            />
          </div>
          <Textarea
            label="Dialogue Text"
            placeholder="Character's spoken line..."
            value={formData.text}
            onChange={(e) => setFormData({ ...formData, text: e.target.value })}
            rows={3}
            required
          />
          <Textarea
            label="Direction (optional)"
            placeholder="e.g., whispered, shouted, sarcastic tone..."
            value={formData.direction}
            onChange={(e) => setFormData({ ...formData, direction: e.target.value })}
            rows={2}
          />
          <Textarea
            label="Audio Prompt (optional)"
            placeholder="TTS prompt: calm female voice, slight reverb, slow pace..."
            value={formData.audio_prompt}
            onChange={(e) => setFormData({ ...formData, audio_prompt: e.target.value })}
            rows={2}
          />
          <div className="flex justify-end gap-3 pt-4 border-t">
            <Button type="button" variant="outline" onClick={() => { setShowCreateModal(false); setEditingDialogue(null); resetForm(); }}>
              Cancel
            </Button>
            <Button type="submit" loading={saving}>
              <Loader2 className="w-4 h-4 mr-2" aria-hidden="true" />
              {editingDialogue ? 'Save Changes' : 'Add Dialogue'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}