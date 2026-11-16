'use client';

import { useEffect, useState } from 'react';
import { useProjectStore } from '@/lib/project-store';
import { api } from '@/lib/api';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { formatDate, getStatusColor } from '@/lib/utils';
import { Plus, Edit, Save, X, BookOpen, Loader2 } from 'lucide-react';

export default function SeriesBiblePage() {
  const { currentProject, seriesBible, fetchSeriesBible, createSeriesBible, updateSeriesBible } = useProjectStore();
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState({
    premise: '',
    main_plot: '',
    tone: '',
    visual_style: '',
    world_settings: '',
    ending_direction: '',
    subplots: '',
    character_relationships: '',
  });

  useEffect(() => {
    if (currentProject) {
      fetchSeriesBible(currentProject.id);
    }
  }, [currentProject, fetchSeriesBible]);

  useEffect(() => {
    if (seriesBible) {
      setFormData({
        premise: seriesBible.premise || '',
        main_plot: seriesBible.main_plot || '',
        tone: seriesBible.tone || '',
        visual_style: seriesBible.visual_style || '',
        world_settings: seriesBible.world_settings || '',
        ending_direction: seriesBible.ending_direction || '',
        subplots: seriesBible.subplots ? JSON.stringify(seriesBible.subplots, null, 2) : '',
        character_relationships: seriesBible.character_relationships ? JSON.stringify(seriesBible.character_relationships, null, 2) : '',
      });
    }
  }, [seriesBible]);

  const handleSave = async () => {
    if (!currentProject) return;
    setSaving(true);
    try {
      const dataToSave = {
        ...formData,
        subplots: formData.subplots ? JSON.parse(formData.subplots) : undefined,
        character_relationships: formData.character_relationships ? JSON.parse(formData.character_relationships) : undefined,
      };
      if (seriesBible) {
        await updateSeriesBible(currentProject.id, dataToSave);
      } else {
        await createSeriesBible(currentProject.id, dataToSave);
      }
      setIsEditing(false);
    } catch (error) {
      console.error('Failed to save series bible:', error);
      alert('Failed to save');
    } finally {
      setSaving(false);
    }
  };

  if (!currentProject) {
    return (
      <div className="text-center py-16">
        <BookOpen className="w-16 h-16 text-gray-300 mx-auto mb-4" aria-hidden="true" />
        <h2 className="text-xl font-semibold text-gray-900 mb-2">No project selected</h2>
        <p className="text-gray-500 mb-4">Select a project from the dashboard to manage its Series Bible</p>
        <Button variant="outline" onClick={() => window.history.back()}>Back to Dashboard</Button>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Series Bible</h1>
          <p className="text-gray-600">Define the core elements of your drama series</p>
        </div>
        <Button variant={isEditing ? 'primary' : 'outline'} onClick={() => setIsEditing(!isEditing)} loading={saving}>
          {isEditing ? (
            <>
              <Save className="w-4 h-4 mr-2" aria-hidden="true" />
              Save Changes
            </>
          ) : (
            <>
              <Edit className="w-4 h-4 mr-2" aria-hidden="true" />
              Edit
            </>
          )}
        </Button>
      </div>

      {seriesBible && !isEditing ? (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Premise</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-gray-700 whitespace-pre-wrap">{seriesBible.premise || 'Not set'}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Main Plot</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-gray-700 whitespace-pre-wrap">{seriesBible.main_plot || 'Not set'}</p>
            </CardContent>
          </Card>

          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Tone</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-gray-700">{seriesBible.tone || 'Not set'}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Visual Style</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-gray-700">{seriesBible.visual_style || 'Not set'}</p>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>World Settings</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-gray-700 whitespace-pre-wrap">{seriesBible.world_settings || 'Not set'}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Ending Direction</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-gray-700 whitespace-pre-wrap">{seriesBible.ending_direction || 'Not set'}</p>
            </CardContent>
          </Card>

          {seriesBible.subplots && seriesBible.subplots.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Subplots</CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="text-sm text-gray-700 whitespace-pre-wrap">{JSON.stringify(seriesBible.subplots, null, 2)}</pre>
              </CardContent>
            </Card>
          )}

          {seriesBible.character_relationships && Object.keys(seriesBible.character_relationships).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Character Relationships</CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="text-sm text-gray-700 whitespace-pre-wrap">{JSON.stringify(seriesBible.character_relationships, null, 2)}</pre>
              </CardContent>
            </Card>
          )}
        </div>
      ) : (
        <Modal isOpen={isEditing} onClose={() => setIsEditing(false)} title="Edit Series Bible" size="xl">
          <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-4">
            <Textarea
              label="Premise"
              placeholder="The core concept of your series in 1-2 sentences..."
              value={formData.premise}
              onChange={(e) => setFormData({ ...formData, premise: e.target.value })}
              rows={3}
              required
            />
            <Textarea
              label="Main Plot"
              placeholder="Detailed description of the main story arc..."
              value={formData.main_plot}
              onChange={(e) => setFormData({ ...formData, main_plot: e.target.value })}
              rows={4}
            />
            <div className="grid gap-4 md:grid-cols-2">
              <Input
                label="Tone"
                placeholder="Dark, comedic, romantic, thrilling..."
                value={formData.tone}
                onChange={(e) => setFormData({ ...formData, tone: e.target.value })}
              />
              <Input
                label="Visual Style"
                placeholder="Cinematic, gritty, colorful, noir..."
                value={formData.visual_style}
                onChange={(e) => setFormData({ ...formData, visual_style: e.target.value })}
              />
            </div>
            <Textarea
              label="World Settings"
              placeholder="Describe the world, time period, rules, society..."
              value={formData.world_settings}
              onChange={(e) => setFormData({ ...formData, world_settings: e.target.value })}
              rows={3}
            />
            <Textarea
              label="Ending Direction"
              placeholder="How does the series end? Tragic, happy, open-ended..."
              value={formData.ending_direction}
              onChange={(e) => setFormData({ ...formData, ending_direction: e.target.value })}
              rows={3}
            />
            <Textarea
              label="Subplots (JSON)"
              placeholder='[{"name": "Romance Arc", "description": "Love story between...", "theme": "love"}]'
              value={formData.subplots}
              onChange={(e) => setFormData({ ...formData, subplots: e.target.value })}
              rows={4}
              helperText="Enter as JSON array"
            />
            <Textarea
              label="Character Relationships (JSON)"
              placeholder='{"protagonist-antagonist": "Rivals since childhood", "protagonist-love_interest": "Complicated history"}'
              value={formData.character_relationships}
              onChange={(e) => setFormData({ ...formData, character_relationships: e.target.value })}
              rows={4}
              helperText="Enter as JSON object"
            />
            <div className="flex justify-end gap-3 pt-4 border-t">
              <Button variant="outline" onClick={() => setIsEditing(false)}>
                Cancel
              </Button>
              <Button onClick={handleSave} loading={saving}>
                <Loader2 className="w-4 h-4 mr-2" aria-hidden="true" />
                Save Series Bible
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}