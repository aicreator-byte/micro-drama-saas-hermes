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
import { Plus, Edit, Save, Trash2, Copy, Loader2, FileText, Sparkles, Download, Filter, ChevronDown, ChevronUp } from 'lucide-react';

const PROMPT_TYPES = [
  'character_image',
  'location_image',
  'scene_image',
  'video_generation',
  'camera_movement',
  'character_action',
  'dialogue_audio',
] as const;

type PromptType = typeof PROMPT_TYPES[number];

const PROMPT_TYPE_LABELS: Record<PromptType, string> = {
  character_image: 'Character Image',
  location_image: 'Location Image',
  scene_image: 'Scene Image',
  video_generation: 'Video Generation',
  camera_movement: 'Camera Movement',
  character_action: 'Character Action',
  dialogue_audio: 'Dialogue Audio',
};

export default function PromptsPage() {
  const { currentProject, prompts, fetchPrompts, createPrompt, updatePrompt, deletePrompt, generatePrompt, generateAllScenePrompts, characters, locations, episodes, scenes, isLoading } = useProjectStore();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingPrompt, setEditingPrompt] = useState<typeof prompts[0] | null>(null);
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [generatingForScene, setGeneratingForScene] = useState<{ episodeId: string; sceneId: string } | null>(null);
  const [filterType, setFilterType] = useState<PromptType | 'all'>('all');
  const [formData, setFormData] = useState({
    title: '',
    prompt_type: 'character_image' as PromptType,
    prompt_text: '',
    negative_prompt: '',
    scene_id: '',
    character_id: '',
    location_id: '',
    episode_id: '',
    parameters: '',
  });
  const [generateFormData, setGenerateFormData] = useState({
    prompt_type: 'character_image' as PromptType,
    context: '',
    style_preferences: '',
  });
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [generatedResult, setGeneratedResult] = useState<{ prompt_text: string; negative_prompt: string | null; parameters: Record<string, unknown> | null } | null>(null);

  useEffect(() => {
    if (currentProject) {
      fetchPrompts(currentProject.id, { prompt_type: filterType === 'all' ? undefined : filterType });
    }
  }, [currentProject, fetchPrompts, filterType]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentProject) return;
    setSaving(true);
    try {
      const params = formData.parameters ? JSON.parse(formData.parameters) : undefined;
      await createPrompt(currentProject.id, {
        ...formData,
        scene_id: formData.scene_id || undefined,
        character_id: formData.character_id || undefined,
        location_id: formData.location_id || undefined,
        episode_id: formData.episode_id || undefined,
        parameters: params,
      });
      setShowCreateModal(false);
      resetForm();
    } catch (error) {
      console.error('Failed to create prompt:', error);
      alert('Failed to create prompt');
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentProject || !editingPrompt) return;
    setSaving(true);
    try {
      const params = formData.parameters ? JSON.parse(formData.parameters) : undefined;
      await updatePrompt(currentProject.id, editingPrompt.id, {
        ...formData,
        scene_id: formData.scene_id || undefined,
        character_id: formData.character_id || undefined,
        location_id: formData.location_id || undefined,
        episode_id: formData.episode_id || undefined,
        parameters: params,
      });
      setEditingPrompt(null);
      resetForm();
    } catch (error) {
      console.error('Failed to update prompt:', error);
      alert('Failed to update prompt');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (promptId: string) => {
    if (!currentProject) return;
    if (!confirm('Are you sure you want to delete this prompt?')) return;
    setDeletingId(promptId);
    try {
      await deletePrompt(currentProject.id, promptId);
    } catch (error) {
      console.error('Failed to delete prompt:', error);
      alert('Failed to delete prompt');
    } finally {
      setDeletingId(null);
    }
  };

  const startEdit = (prompt: typeof prompts[0]) => {
    setEditingPrompt(prompt);
    setFormData({
      title: prompt.title,
      prompt_type: prompt.prompt_type,
      prompt_text: prompt.prompt_text,
      negative_prompt: prompt.negative_prompt || '',
      scene_id: prompt.scene_id || '',
      character_id: prompt.character_id || '',
      location_id: prompt.location_id || '',
      episode_id: prompt.episode_id || '',
      parameters: prompt.parameters ? JSON.stringify(prompt.parameters, null, 2) : '',
    });
  };

  const resetForm = () => {
    setFormData({
      title: '',
      prompt_type: 'character_image',
      prompt_text: '',
      negative_prompt: '',
      scene_id: '',
      character_id: '',
      location_id: '',
      episode_id: '',
      parameters: '',
    });
  };

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    setGenerating(true);
    try {
      const context = generateFormData.context ? JSON.parse(generateFormData.context) : {};
      const style = generateFormData.style_preferences ? JSON.parse(generateFormData.style_preferences) : {};
      const result = await generatePrompt({
        prompt_type: generateFormData.prompt_type,
        context,
        style_preferences: style,
      });
      setGeneratedResult(result);
      // Pre-fill form with generated result
      setFormData(prev => ({
        ...prev,
        prompt_type: generateFormData.prompt_type,
        prompt_text: result.prompt_text,
        negative_prompt: result.negative_prompt || '',
        parameters: result.parameters ? JSON.stringify(result.parameters, null, 2) : '',
      }));
    } catch (error) {
      console.error('Failed to generate prompt:', error);
      alert('Failed to generate prompt');
    } finally {
      setGenerating(false);
    }
  };

  const handleGenerateAllForScene = async (episodeId: string, sceneId: string) => {
    if (!currentProject) return;
    setGeneratingForScene({ episodeId, sceneId });
    try {
      await generateAllScenePrompts(currentProject.id, episodeId, sceneId);
      alert('Generated all prompts for this scene!');
    } catch (error) {
      console.error('Failed to generate scene prompts:', error);
      alert('Failed to generate scene prompts');
    } finally {
      setGeneratingForScene(null);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    alert('Copied to clipboard!');
  };

  const exportPrompts = () => {
    const data = prompts.map(p => ({
      title: p.title,
      prompt_type: p.prompt_type,
      prompt_text: p.prompt_text,
      negative_prompt: p.negative_prompt,
      parameters: p.parameters,
    }));
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `prompts-${currentProject?.title || 'project'}-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!currentProject) {
    return (
      <div className="text-center py-16">
        <FileText className="w-16 h-16 text-gray-300 mx-auto mb-4" aria-hidden="true" />
        <h2 className="text-xl font-semibold text-gray-900 mb-2">No project selected</h2>
        <p className="text-gray-500 mb-4">Select a project from the dashboard to manage prompts</p>
      </div>
    );
  }

  const filteredPrompts = filterType === 'all' ? prompts : prompts.filter(p => p.prompt_type === filterType);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Prompt Studio</h1>
          <p className="text-gray-600">Create, manage, and generate AI prompts for your production</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={() => { resetForm(); setShowCreateModal(true); }} variant="outline">
            <Plus className="w-4 h-4 mr-2" aria-hidden="true" />
            Create Prompt
          </Button>
          <Button onClick={() => { setShowGenerateModal(true); setGeneratedResult(null); }} variant="outline">
            <Sparkles className="w-4 h-4 mr-2" aria-hidden="true" />
            Generate with AI
          </Button>
          <Button onClick={exportPrompts} variant="outline">
            <Download className="w-4 h-4 mr-2" aria-hidden="true" />
            Export
          </Button>
        </div>
      </div>

      {/* Filter */}
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm font-medium text-gray-700">
          <Filter className="w-4 h-4" aria-hidden="true" />
          Filter by type:
        </label>
        <Select value={filterType} onValueChange={setFilterType as any}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="All types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            {PROMPT_TYPES.map(type => (
              <SelectItem key={type} value={type}>{PROMPT_TYPE_LABELS[type]}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="text-sm text-gray-500">{filteredPrompts.length} of {prompts.length} prompts</span>
      </div>

      {filteredPrompts.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center">
            <FileText className="w-16 h-16 text-gray-300 mx-auto mb-4" aria-hidden="true" />
            <h3 className="text-lg font-medium text-gray-900 mb-1">No prompts yet</h3>
            <p className="text-gray-500 mb-4">Create prompts manually or generate them with AI</p>
            <div className="flex justify-center gap-2">
              <Button onClick={() => { resetForm(); setShowCreateModal(true); }}>
                <Plus className="w-4 h-4 mr-2" aria-hidden="true" />
                Create Prompt
              </Button>
              <Button onClick={() => { setShowGenerateModal(true); setGeneratedResult(null); }} variant="outline">
                <Sparkles className="w-4 h-4 mr-2" aria-hidden="true" />
                Generate with AI
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {filteredPrompts.map((prompt) => (
            <Card
              key={prompt.id}
              className={cn('group', editingPrompt?.id === prompt.id && 'ring-2 ring-purple-500')}
            >
              <CardContent className="p-4">
                <div className="flex items-start gap-4">
                  <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center text-white flex-shrink-0', {
                    'bg-purple-500': prompt.prompt_type === 'character_image',
                    'bg-green-500': prompt.prompt_type === 'location_image',
                    'bg-blue-500': prompt.prompt_type === 'scene_image',
                    'bg-orange-500': prompt.prompt_type === 'video_generation',
                    'bg-pink-500': prompt.prompt_type === 'camera_movement',
                    'bg-indigo-500': prompt.prompt_type === 'character_action',
                    'bg-teal-500': prompt.prompt_type === 'dialogue_audio',
                  })}>
                    <FileText className="w-5 h-5" aria-hidden="true" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-gray-900">{prompt.title}</h3>
                      <Badge variant="purple" className="text-xs capitalize">
                        {PROMPT_TYPE_LABELS[prompt.prompt_type as PromptType].replace('_', ' ')}
                      </Badge>
                    </div>
                    <p className="mt-1 text-sm text-gray-500 line-clamp-2 font-mono text-xs">
                      {prompt.prompt_text.slice(0, 150)}...
                    </p>
                    <div className="mt-2 flex flex-wrap gap-1.5 text-xs text-gray-500">
                      {prompt.scene_id && <span className="bg-gray-100 px-2 py-0.5 rounded">Scene</span>}
                      {prompt.character_id && <span className="bg-gray-100 px-2 py-0.5 rounded">Character</span>}
                      {prompt.location_id && <span className="bg-gray-100 px-2 py-0.5 rounded">Location</span>}
                      {prompt.episode_id && <span className="bg-gray-100 px-2 py-0.5 rounded">Episode</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => copyToClipboard(prompt.prompt_text)}
                      className="p-2 text-gray-400 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                      aria-label="Copy prompt"
                    >
                      <Copy className="w-4 h-4" aria-hidden="true" />
                    </button>
                    <button
                      onClick={() => startEdit(prompt)}
                      className="p-2 text-gray-400 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                      aria-label="Edit prompt"
                    >
                      <Edit className="w-4 h-4" aria-hidden="true" />
                    </button>
                    <button
                      onClick={() => handleDelete(prompt.id)}
                      disabled={deletingId === prompt.id}
                      className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50"
                      aria-label="Delete prompt"
                    >
                      {deletingId === prompt.id ? (
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
        isOpen={showCreateModal || !!editingPrompt}
        onClose={() => { setShowCreateModal(false); setEditingPrompt(null); resetForm(); }}
        title={editingPrompt ? 'Edit Prompt' : 'Create Prompt'}
        size="xl"
      >
        <form onSubmit={editingPrompt ? handleUpdate : handleCreate} className="space-y-4 max-h-[80vh] overflow-y-auto pr-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Input
              label="Title"
              placeholder="Prompt title"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              required
            />
            <Select value={formData.prompt_type} onValueChange={(v) => setFormData({ ...formData, prompt_type: v as PromptType })}>
              <SelectTrigger>
                <SelectValue placeholder="Select prompt type" />
              </SelectTrigger>
              <SelectContent>
                {PROMPT_TYPES.map(type => (
                  <SelectItem key={type} value={type}>{PROMPT_TYPE_LABELS[type]}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Select
              value={formData.scene_id}
              onValueChange={(v) => setFormData({ ...formData, scene_id: v })}
              placeholder="Select scene (optional)"
            >
              <SelectTrigger>
                <SelectValue placeholder="Scene" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">None</SelectItem>
                {Object.values(scenes).flat().map(scene => (
                  <SelectItem key={scene.id} value={scene.id}>
                    Ep {scene.episode_id?.slice(-4)} - Scene {scene.scene_number}: {scene.title || 'Untitled'}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={formData.character_id}
              onValueChange={(v) => setFormData({ ...formData, character_id: v })}
              placeholder="Select character (optional)"
            >
              <SelectTrigger>
                <SelectValue placeholder="Character" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">None</SelectItem>
                {characters.map(char => (
                  <SelectItem key={char.id} value={char.id}>{char.name} ({char.role || 'No role'})</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Select
              value={formData.location_id}
              onValueChange={(v) => setFormData({ ...formData, location_id: v })}
              placeholder="Select location (optional)"
            >
              <SelectTrigger>
                <SelectValue placeholder="Location" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">None</SelectItem>
                {locations.map(loc => (
                  <SelectItem key={loc.id} value={loc.id}>{loc.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={formData.episode_id}
              onValueChange={(v) => setFormData({ ...formData, episode_id: v })}
              placeholder="Select episode (optional)"
            >
              <SelectTrigger>
                <SelectValue placeholder="Episode" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">None</SelectItem>
                {episodes.map(ep => (
                  <SelectItem key={ep.id} value={ep.id}>Episode {ep.episode_number}: {ep.title || 'Untitled'}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Textarea
            label="Prompt Text"
            placeholder="Enter the prompt text..."
            value={formData.prompt_text}
            onChange={(e) => setFormData({ ...formData, prompt_text: e.target.value })}
            rows={4}
            required
          />
          <Textarea
            label="Negative Prompt"
            placeholder="What to avoid in generation..."
            value={formData.negative_prompt}
            onChange={(e) => setFormData({ ...formData, negative_prompt: e.target.value })}
            rows={2}
          />
          <Textarea
            label="Parameters (JSON)"
            placeholder='{"width": 1024, "height": 1024, "steps": 30, "cfg_scale": 7.0}'
            value={formData.parameters}
            onChange={(e) => setFormData({ ...formData, parameters: e.target.value })}
            rows={3}
            fontMono
          />
          <div className="flex justify-end gap-3 pt-4 border-t">
            <Button type="button" variant="outline" onClick={() => { setShowCreateModal(false); setEditingPrompt(null); resetForm(); }}>
              Cancel
            </Button>
            <Button type="submit" loading={saving}>
              <Loader2 className="w-4 h-4 mr-2" aria-hidden="true" />
              {editingPrompt ? 'Save Changes' : 'Create Prompt'}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Generate with AI Modal */}
      <Modal
        isOpen={showGenerateModal}
        onClose={() => { setShowGenerateModal(false); setGeneratedResult(null); }}
        title="Generate Prompt with AI"
        size="lg"
      >
        <div className="space-y-4 max-h-[80vh] overflow-y-auto pr-4">
          <form onSubmit={handleGenerate} className="space-y-4">
            <Select
              value={generateFormData.prompt_type}
              onValueChange={(v) => setGenerateFormData({ ...generateFormData, prompt_type: v as PromptType })}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select prompt type" />
              </SelectTrigger>
              <SelectContent>
                {PROMPT_TYPES.map(type => (
                  <SelectItem key={type} value={type}>{PROMPT_TYPE_LABELS[type]}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Textarea
              label="Context (JSON)"
              placeholder='{"name": "Hero", "physical_appearance": "tall, dark hair", "personality": "brave", "costume": "leather jacket"}'
              value={generateFormData.context}
              onChange={(e) => setGenerateFormData({ ...generateFormData, context: e.target.value })}
              rows={4}
              fontMono
            />
            <Textarea
              label="Style Preferences (JSON, optional)"
              placeholder='{"lighting": "cinematic", "parameters": {"width": 1920, "height": 1080}}'
              value={generateFormData.style_preferences}
              onChange={(e) => setGenerateFormData({ ...generateFormData, style_preferences: e.target.value })}
              rows={3}
              fontMono
            />
            <div className="flex justify-end gap-3 pt-4 border-t">
              <Button type="button" variant="outline" onClick={() => { setShowGenerateModal(false); setGeneratedResult(null); }}>
                Cancel
              </Button>
              <Button type="submit" loading={generating}>
                <Loader2 className="w-4 h-4 mr-2" aria-hidden="true" />
                Generate
              </Button>
            </div>
          </form>

          {generatedResult && (
            <div className="border-t pt-4">
              <h4 className="font-medium text-gray-900 mb-2">Generated Result</h4>
              <div className="space-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Prompt Text</label>
                  <div className="flex gap-2">
                    <Textarea
                      value={generatedResult.prompt_text}
                      onChange={() => {}}
                      rows={3}
                      fontMono
                      readOnly
                    />
                    <button
                      onClick={() => copyToClipboard(generatedResult.prompt_text)}
                      className="self-start p-2 text-gray-400 hover:text-purple-600"
                      aria-label="Copy generated prompt"
                    >
                      <Copy className="w-4 h-4" aria-hidden="true" />
                    </button>
                  </div>
                </div>
                {generatedResult.negative_prompt && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Negative Prompt</label>
                    <Textarea
                      value={generatedResult.negative_prompt}
                      onChange={() => {}}
                      rows={2}
                      fontMono
                      readOnly
                    />
                  </div>
                )}
                {generatedResult.parameters && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Parameters</label>
                    <Textarea
                      value={JSON.stringify(generatedResult.parameters, null, 2)}
                      onChange={() => {}}
                      rows={3}
                      fontMono
                      readOnly
                    />
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
}