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
import { Plus, Edit, Save, Trash2, MapPin, Loader2, GripVertical } from 'lucide-react';

export default function LocationsPage() {
  const { currentProject, locations, fetchLocations, createLocation, updateLocation, deleteLocation, reorderLocations, isLoading } = useProjectStore();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingLocation, setEditingLocation] = useState<typeof locations[0] | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    environment: '',
    lighting: '',
    atmosphere: '',
    consistency_instructions: '',
  });
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [dragIndex, setDragIndex] = useState<number | null>(null);

  useEffect(() => {
    if (currentProject) {
      fetchLocations(currentProject.id);
    }
  }, [currentProject, fetchLocations]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentProject) return;
    setSaving(true);
    try {
      await createLocation(currentProject.id, formData);
      setShowCreateModal(false);
      resetForm();
    } catch (error) {
      console.error('Failed to create location:', error);
      alert('Failed to create location');
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentProject || !editingLocation) return;
    setSaving(true);
    try {
      await updateLocation(currentProject.id, editingLocation.id, formData);
      setEditingLocation(null);
      resetForm();
    } catch (error) {
      console.error('Failed to update location:', error);
      alert('Failed to update location');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (locationId: string) => {
    if (!currentProject) return;
    if (!confirm('Are you sure you want to delete this location?')) return;
    setDeletingId(locationId);
    try {
      await deleteLocation(currentProject.id, locationId);
    } catch (error) {
      console.error('Failed to delete location:', error);
      alert('Failed to delete location');
    } finally {
      setDeletingId(null);
    }
  };

  const startEdit = (location: typeof locations[0]) => {
    setEditingLocation(location);
    setFormData({
      name: location.name,
      description: location.description || '',
      environment: location.environment || '',
      lighting: location.lighting || '',
      atmosphere: location.atmosphere || '',
      consistency_instructions: location.consistency_instructions || '',
    });
  };

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      environment: '',
      lighting: '',
      atmosphere: '',
      consistency_instructions: '',
    });
  };

  const handleDragStart = (index: number) => {
    setDragIndex(index);
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    if (dragIndex !== null && dragIndex !== index) {
      setDragIndex(index);
    }
  };

  const handleDragEnd = () => {
    setDragIndex(null);
  };

  if (!currentProject) {
    return (
      <div className="text-center py-16">
        <MapPin className="w-16 h-16 text-gray-300 mx-auto mb-4" aria-hidden="true" />
        <h2 className="text-xl font-semibold text-gray-900 mb-2">No project selected</h2>
        <p className="text-gray-500 mb-4">Select a project from the dashboard to manage locations</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Locations</h1>
          <p className="text-gray-600">Create and manage shooting locations</p>
        </div>
        <Button onClick={() => { resetForm(); setShowCreateModal(true); }}>
          <Plus className="w-4 h-4 mr-2" aria-hidden="true" />
          Add Location
        </Button>
      </div>

      {locations.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center">
            <MapPin className="w-16 h-16 text-gray-300 mx-auto mb-4" aria-hidden="true" />
            <h3 className="text-lg font-medium text-gray-900 mb-1">No locations yet</h3>
            <p className="text-gray-500 mb-4">Create locations for your drama series</p>
            <Button onClick={() => setShowCreateModal(true)}>
              <Plus className="w-4 h-4 mr-2" aria-hidden="true" />
              Add Location
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {locations.map((location, index) => (
            <Card
              key={location.id}
              className={cn('group', dragIndex === index && 'opacity-50 ring-2 ring-purple-500')}
              draggable
              onDragStart={() => handleDragStart(index)}
              onDragOver={(e) => handleDragOver(e, index)}
              onDragEnd={handleDragEnd}
            >
              <CardContent className="p-4">
                <div className="flex items-start gap-4">
                  <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center text-blue-600 flex-shrink-0">
                    <MapPin className="w-5 h-5" aria-hidden="true" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-gray-900">{location.name}</h3>
                      <Badge variant="purple" className="text-xs">#{location.order_index + 1}</Badge>
                    </div>
                    <p className="mt-1 text-sm text-gray-500 line-clamp-2">
                      {location.description || 'No description'}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-1.5 text-xs text-gray-500">
                      {location.environment && <span className="bg-gray-100 px-2 py-0.5 rounded">Env: {location.environment.slice(0, 30)}...</span>}
                      {location.lighting && <Badge variant="default" className="text-xs">{location.lighting}</Badge>}
                      {location.atmosphere && <Badge variant="default" className="text-xs">{location.atmosphere}</Badge>}
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => startEdit(location)}
                      className="p-2 text-gray-400 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                      aria-label="Edit location"
                    >
                      <Edit className="w-4 h-4" aria-hidden="true" />
                    </button>
                    <button
                      onClick={() => handleDelete(location.id)}
                      disabled={deletingId === location.id}
                      className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50"
                      aria-label="Delete location"
                    >
                      {deletingId === location.id ? (
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
        isOpen={showCreateModal || !!editingLocation}
        onClose={() => { setShowCreateModal(false); setEditingLocation(null); resetForm(); }}
        title={editingLocation ? 'Edit Location' : 'Create Location'}
        size="lg"
      >
        <form onSubmit={editingLocation ? handleUpdate : handleCreate} className="space-y-4 max-h-[80vh] overflow-y-auto pr-4">
          <Input
            label="Location Name"
            placeholder="e.g., Downtown Coffee Shop"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            required
          />
          <Textarea
            label="Description"
            placeholder="General description of the location..."
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            rows={3}
          />
          <div className="grid gap-4 md:grid-cols-2">
            <Input
              label="Environment"
              placeholder="Interior, exterior, urban, rural, sci-fi..."
              value={formData.environment}
              onChange={(e) => setFormData({ ...formData, environment: e.target.value })}
            />
            <Input
              label="Lighting"
              placeholder="Natural, neon, dim, golden hour, studio..."
              value={formData.lighting}
              onChange={(e) => setFormData({ ...formData, lighting: e.target.value })}
            />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Input
              label="Atmosphere"
              placeholder="Tense, peaceful, romantic, eerie..."
              value={formData.atmosphere}
              onChange={(e) => setFormData({ ...formData, atmosphere: e.target.value })}
            />
          </div>
          <Textarea
            label="Consistency Instructions"
            placeholder="Guidelines for maintaining location consistency across scenes..."
            value={formData.consistency_instructions}
            onChange={(e) => setFormData({ ...formData, consistency_instructions: e.target.value })}
            rows={2}
          />
          <div className="flex justify-end gap-3 pt-4 border-t">
            <Button type="button" variant="outline" onClick={() => { setShowCreateModal(false); setEditingLocation(null); resetForm(); }}>
              Cancel
            </Button>
            <Button type="submit" loading={saving}>
              <Loader2 className="w-4 h-4 mr-2" aria-hidden="true" />
              {editingLocation ? 'Save Changes' : 'Create Location'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}