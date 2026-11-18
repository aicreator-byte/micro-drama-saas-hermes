'use client';

import { useEffect, useState } from 'react';
import { useProjectStore } from '@/lib/project-store';
import { api } from '@/lib/api';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { formatDate, cn } from '@/lib/utils';
import { Plus, Edit, Save, Trash2, User, Loader2, GripVertical } from 'lucide-react';

export default function CharactersPage() {
  const { currentProject, characters, fetchCharacters, createCharacter, updateCharacter, deleteCharacter, reorderCharacters, isLoading } = useProjectStore();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingCharacter, setEditingCharacter] = useState<typeof characters[0] | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    role: '',
    physical_appearance: '',
    personality: '',
    background: '',
    costume: '',
    consistency_instructions: '',
  });
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [dragIndex, setDragIndex] = useState<number | null>(null);

  useEffect(() => {
    if (currentProject) {
      fetchCharacters(currentProject.id);
    }
  }, [currentProject, fetchCharacters]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentProject) return;
    setSaving(true);
    try {
      await createCharacter(currentProject.id, formData);
      setShowCreateModal(false);
      resetForm();
    } catch (error) {
      console.error('Failed to create character:', error);
      alert('Failed to create character');
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentProject || !editingCharacter) return;
    setSaving(true);
    try {
      await updateCharacter(currentProject.id, editingCharacter.id, formData);
      setEditingCharacter(null);
      resetForm();
    } catch (error) {
      console.error('Failed to update character:', error);
      alert('Failed to update character');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (characterId: string) => {
    if (!currentProject) return;
    if (!confirm('Are you sure you want to delete this character?')) return;
    setDeletingId(characterId);
    try {
      await deleteCharacter(currentProject.id, characterId);
    } catch (error) {
      console.error('Failed to delete character:', error);
      alert('Failed to delete character');
    } finally {
      setDeletingId(null);
    }
  };

  const startEdit = (character: typeof characters[0]) => {
    setEditingCharacter(character);
    setFormData({
      name: character.name,
      role: character.role || '',
      physical_appearance: character.physical_appearance || '',
      personality: character.personality || '',
      background: character.background || '',
      costume: character.costume || '',
      consistency_instructions: character.consistency_instructions || '',
    });
  };

  const resetForm = () => {
    setFormData({
      name: '',
      role: '',
      physical_appearance: '',
      personality: '',
      background: '',
      costume: '',
      consistency_instructions: '',
    });
  };

  const handleDragStart = (index: number) => {
    setDragIndex(index);
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    if (dragIndex !== null && dragIndex !== index) {
      const newCharacters = [...characters];
      const [removed] = newCharacters.splice(dragIndex, 1);
      newCharacters.splice(index, 0, removed);
      // Update order indices
      newCharacters.forEach((c, i) => (c.order_index = i));
      // This would need a reorder API call in real app
      setDragIndex(index);
    }
  };

  const handleDragEnd = () => {
    setDragIndex(null);
  };

  if (!currentProject) {
    return (
      <div className="text-center py-16">
        <User className="w-16 h-16 text-gray-300 mx-auto mb-4" aria-hidden="true" />
        <h2 className="text-xl font-semibold text-gray-900 mb-2">No project selected</h2>
        <p className="text-gray-500 mb-4">Select a project from the dashboard to manage characters</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Characters</h1>
          <p className="text-gray-600">Create and manage characters for your project</p>
        </div>
        <Button onClick={() => { resetForm(); setShowCreateModal(true); }}>
          <Plus className="w-4 h-4 mr-2" aria-hidden="true" />
          Add Character
        </Button>
      </div>

      {characters.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center">
            <User className="w-16 h-16 text-gray-300 mx-auto mb-4" aria-hidden="true" />
            <h3 className="text-lg font-medium text-gray-900 mb-1">No characters yet</h3>
            <p className="text-gray-500 mb-4">Create characters for your drama series</p>
            <Button onClick={() => setShowCreateModal(true)}>
              <Plus className="w-4 h-4 mr-2" aria-hidden="true" />
              Add Character
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {characters.map((character, index) => (
            <Card
              key={character.id}
              className={cn('group', dragIndex === index && 'opacity-50 ring-2 ring-purple-500')}
              draggable
              onDragStart={() => handleDragStart(index)}
              onDragOver={(e) => handleDragOver(e, index)}
              onDragEnd={handleDragEnd}
            >
              <CardContent className="p-4">
                <div className="flex items-start gap-4">
                  <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center text-purple-600 flex-shrink-0">
                    <User className="w-5 h-5" aria-hidden="true" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-gray-900">{character.name}</h3>
                      {character.role && <Badge variant="info" className="text-xs">{character.role}</Badge>}
                      <Badge variant="purple" className="text-xs">#{character.order_index + 1}</Badge>
                    </div>
                    <p className="mt-1 text-sm text-gray-500 line-clamp-2">
                      {character.physical_appearance || 'No appearance description'}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-1.5 text-xs text-gray-500">
                      {character.personality && <span className="bg-gray-100 px-2 py-0.5 rounded">Personality: {character.personality.slice(0, 30)}...</span>}
                      {character.background && <span className="bg-gray-100 px-2 py-0.5 rounded">Background: {character.background.slice(0, 30)}...</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => startEdit(character)}
                      className="p-2 text-gray-400 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                      aria-label="Edit character"
                    >
                      <Edit className="w-4 h-4" aria-hidden="true" />
                    </button>
                    <button
                      onClick={() => handleDelete(character.id)}
                      disabled={deletingId === character.id}
                      className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50"
                      aria-label="Delete character"
                    >
                      {deletingId === character.id ? (
                        <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
                      ) : (
                        <Trash2 className="w-4 h-4" aria-hidden="true" />
                      )}
                    </button>
                    <button
                      className="p-2 text-gray-400 hover:text-gray-600 cursor-grab active:cursor-grabbing"
                      aria-label="Drag to reorder"
                    >
                      <GripVertical className="w-5 h-5" aria-hidden="true" />
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
        isOpen={showCreateModal || !!editingCharacter}
        onClose={() => { setShowCreateModal(false); setEditingCharacter(null); resetForm(); }}
        title={editingCharacter ? 'Edit Character' : 'Create Character'}
        size="lg"
      >
        <form onSubmit={editingCharacter ? handleUpdate : handleCreate} className="space-y-4 max-h-[80vh] overflow-y-auto pr-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Input
              label="Name"
              placeholder="Character name"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
            />
            <Input
              label="Role"
              placeholder="Protagonist, Antagonist, Support..."
              value={formData.role}
              onChange={(e) => setFormData({ ...formData, role: e.target.value })}
            />
          </div>
          <Textarea
            label="Physical Appearance"
            placeholder="Detailed physical description..."
            value={formData.physical_appearance}
            onChange={(e) => setFormData({ ...formData, physical_appearance: e.target.value })}
            rows={3}
          />
          <Textarea
            label="Personality"
            placeholder="Personality traits, quirks, motivations..."
            value={formData.personality}
            onChange={(e) => setFormData({ ...formData, personality: e.target.value })}
            rows={3}
          />
          <Textarea
            label="Background"
            placeholder="Character history, upbringing, key events..."
            value={formData.background}
            onChange={(e) => setFormData({ ...formData, background: e.target.value })}
            rows={3}
          />
          <Textarea
            label="Costume"
            placeholder="Clothing style, signature items, accessories..."
            value={formData.costume}
            onChange={(e) => setFormData({ ...formData, costume: e.target.value })}
            rows={2}
          />
          <Textarea
            label="Consistency Instructions"
            placeholder="Guidelines for maintaining character consistency across scenes..."
            value={formData.consistency_instructions}
            onChange={(e) => setFormData({ ...formData, consistency_instructions: e.target.value })}
            rows={2}
          />
          <div className="flex justify-end gap-3 pt-4 border-t">
            <Button type="button" variant="outline" onClick={() => { setShowCreateModal(false); setEditingCharacter(null); resetForm(); }}>
              Cancel
            </Button>
            <Button type="submit" loading={saving}>
              <Loader2 className="w-4 h-4 mr-2" aria-hidden="true" />
              {editingCharacter ? 'Save Changes' : 'Create Character'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}