'use client';

import { useEffect, useState } from 'react';
import { useProjectStore } from '@/lib/project-store';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/Select';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { formatDate, cn } from '@/lib/utils';
import { Plus, Edit, Save, Trash2, FileText, Download, Upload, Loader2, Sparkles, ArrowRightLeft, Eye, Zap, ExternalLink, ChevronDown, ChevronUp } from 'lucide-react';

const TASK_TYPES = [
  'image_generation',
  'video_generation',
  'prompt_preparation',
  'reference_collection',
  'asset_organization',
  'custom',
] as const;

type TaskType = typeof TASK_TYPES[number];

const TASK_TYPE_LABELS: Record<TaskType, string> = {
  image_generation: 'Image Generation',
  video_generation: 'Video Generation',
  prompt_preparation: 'Prompt Preparation',
  reference_collection: 'Reference Collection',
  asset_organization: 'Asset Organization',
  custom: 'Custom Task',
};

const STATUS_LABELS: Record<string, string> = {
  pending: 'Pending',
  in_progress: 'In Progress',
  completed: 'Completed',
  failed: 'Failed',
  exported: 'Exported',
  imported: 'Imported',
};

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-gray-100 text-gray-800',
  in_progress: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  exported: 'bg-purple-100 text-purple-800',
  imported: 'bg-indigo-100 text-indigo-800',
};

export default function FlowPage() {
  const { currentProject, flowTasks, fetchFlowTasks, createFlowTask, updateFlowTask, deleteFlowTask, exportPromptsForFlow, importFlowResults, episodes, scenes, googleAccounts } = useProjectStore();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingTask, setEditingTask] = useState<typeof flowTasks[0] | null>(null);
  const [exportModal, setExportModal] = useState(false);
  const [importModal, setImportModal] = useState<string | null>(null);
  const [importFiles, setImportFiles] = useState<string>('[]');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [filterType, setFilterType] = useState<TaskType | 'all'>('all');
  const [formData, setFormData] = useState<{
    task_type: TaskType;
    title: string;
    description: string;
    episode_id: string;
    scene_id: string;
    google_account_id: string;
    input_prompts: string;
    reference_assets: string;
  }>({
    task_type: 'prompt_preparation',
    title: '',
    description: '',
    episode_id: '',
    scene_id: '',
    google_account_id: '',
    input_prompts: '[]',
    reference_assets: '[]',
  });
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [importingId, setImportingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [exportResult, setExportResult] = useState<any>(null);

  useEffect(() => {
    if (currentProject) {
      fetchFlowTasks(currentProject.id);
    }
  }, [currentProject, fetchFlowTasks]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentProject) return;
    setSaving(true);
    try {
      const inputPrompts = formData.input_prompts ? JSON.parse(formData.input_prompts) : [];
      const referenceAssets = formData.reference_assets ? JSON.parse(formData.reference_assets) : [];
      await createFlowTask(currentProject.id, {
        ...formData,
        episode_id: formData.episode_id || undefined,
        scene_id: formData.scene_id || undefined,
        google_account_id: formData.google_account_id || undefined,
        input_prompts: inputPrompts,
        reference_assets: referenceAssets,
      });
      setShowCreateModal(false);
      resetForm();
    } catch (error) {
      console.error('Failed to create flow task:', error);
      alert('Failed to create flow task');
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentProject || !editingTask) return;
    setSaving(true);
    try {
      const inputPrompts = formData.input_prompts ? JSON.parse(formData.input_prompts) : [];
      const referenceAssets = formData.reference_assets ? JSON.parse(formData.reference_assets) : [];
      await updateFlowTask(currentProject.id, editingTask.id, {
        ...formData,
        episode_id: formData.episode_id || undefined,
        scene_id: formData.scene_id || undefined,
        google_account_id: formData.google_account_id || undefined,
        input_prompts: inputPrompts,
        reference_assets: referenceAssets,
      });
      setEditingTask(null);
      resetForm();
    } catch (error) {
      console.error('Failed to update flow task:', error);
      alert('Failed to update flow task');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (taskId: string) => {
    if (!currentProject) return;
    if (!confirm('Are you sure you want to delete this flow task?')) return;
    setDeletingId(taskId);
    try {
      await deleteFlowTask(currentProject.id, taskId);
    } catch (error) {
      console.error('Failed to delete flow task:', error);
      alert('Failed to delete flow task');
    } finally {
      setDeletingId(null);
    }
  };

  const handleExport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentProject) return;
    setExporting(true);
    try {
      const episodeId = formData.episode_id || undefined;
      const sceneIds = formData.scene_id ? [formData.scene_id] : undefined;
      const result = await exportPromptsForFlow(currentProject.id, episodeId, sceneIds);
      setExportResult(result);
      // Download the exported data
      const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `flow-export-${currentProject.title}-${new Date().toISOString().split('T')[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setExportModal(false);
    } catch (error) {
      console.error('Failed to export prompts:', error);
      alert('Failed to export prompts');
    } finally {
      setExporting(false);
    }
  };

  const handleImport = async (taskId: string) => {
    if (!currentProject) return;
    setImportingId(taskId);
    try {
      const outputFiles = importFiles ? JSON.parse(importFiles) : [];
      await importFlowResults(currentProject.id, taskId, outputFiles);
      alert('Flow results imported successfully!');
      setImportModal(null);
      setImportFiles('[]');
    } catch (error) {
      console.error('Failed to import flow results:', error);
      alert('Failed to import flow results');
    } finally {
      setImportingId(null);
    }
  };

  const startEdit = (task: typeof flowTasks[0]) => {
    setEditingTask(task);
    setFormData({
      task_type: task.task_type as TaskType,
      title: task.title,
      description: task.description || '',
      episode_id: task.episode_id || '',
      scene_id: task.scene_id || '',
      google_account_id: task.google_account_id || '',
      input_prompts: task.input_prompts ? JSON.stringify(task.input_prompts, null, 2) : '[]',
      reference_assets: task.reference_assets ? JSON.stringify(task.reference_assets, null, 2) : '[]',
    });
  };

  const startImport = (taskId: string) => {
    setImportModal(taskId);
    setImportFiles('[]');
  };

  const resetForm = () => {
    setFormData({
      task_type: 'prompt_preparation',
      title: '',
      description: '',
      episode_id: '',
      scene_id: '',
      google_account_id: '',
      input_prompts: '[]',
      reference_assets: '[]',
    });
  };

  const filteredTasks = flowTasks.filter(task => {
    const statusMatch = filterStatus === 'all' || task.status === filterStatus;
    const typeMatch = filterType === 'all' || task.task_type === filterType;
    return statusMatch && typeMatch;
  });

  if (!currentProject) {
    return (
      <div className="text-center py-16">
        <Zap className="w-16 h-16 text-gray-300 mx-auto mb-4" aria-hidden="true" />
        <h2 className="text-xl font-semibold text-gray-900 mb-2">No project selected</h2>
        <p className="text-gray-500 mb-4">Select a project from the dashboard to manage Flow Bridge tasks</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Flow Bridge</h1>
          <p className="text-gray-600">Organize production tasks for Google Flow. Export prompts, track manual work, import results.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={() => { resetForm(); setShowCreateModal(true); }}>
            <Plus className="w-4 h-4 mr-2" aria-hidden="true" />
            Create Task
          </Button>
          <Button onClick={() => { resetForm(); setExportModal(true); setFormData({ ...formData, episode_id: '', scene_id: '' }); }} variant="outline">
            <Download className="w-4 h-4 mr-2" aria-hidden="true" />
            Export Prompts
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <Select value={filterStatus} onValueChange={setFilterStatus}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            {Object.entries(STATUS_LABELS).map(([key, label]) => (
              <SelectItem key={key} value={key}>{label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={filterType} onValueChange={setFilterType as any}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="All types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            {TASK_TYPES.map(type => (
              <SelectItem key={type} value={type}>{TASK_TYPE_LABELS[type]}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="text-sm text-gray-500">{filteredTasks.length} of {flowTasks.length} tasks</span>
      </div>

      {filteredTasks.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center">
            <Zap className="w-16 h-16 text-gray-300 mx-auto mb-4" aria-hidden="true" />
            <h3 className="text-lg font-medium text-gray-900 mb-1">No flow tasks yet</h3>
            <p className="text-gray-500 mb-4">Create tasks to organize your Google Flow production workflow</p>
            <Button onClick={() => setShowCreateModal(true)}>
              <Plus className="w-4 h-4 mr-2" aria-hidden="true" />
              Create Task
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {filteredTasks.map((task) => (
            <Card
              key={task.id}
              className={cn('group', editingTask?.id === task.id && 'ring-2 ring-purple-500')}
            >
              <CardContent className="p-4">
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center text-purple-600 flex-shrink-0">
                    <Zap className="w-6 h-6" aria-hidden="true" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-gray-900">{task.title}</h3>
                      <Badge variant="purple" className="text-xs capitalize">
                        {TASK_TYPE_LABELS[task.task_type as TaskType] || task.task_type}
                      </Badge>
                    </div>
                    {task.description && (
                      <p className="mt-1 text-sm text-gray-500 line-clamp-2">{task.description}</p>
                    )}
                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-gray-500">
                      <span className={cn('px-2 py-0.5 rounded-full', STATUS_COLORS[task.status])} style={{ fontSize: '0.65rem' }}>
                        {STATUS_LABELS[task.status] || task.status}
                      </span>
                      {task.episode_id && <span className="bg-gray-100 px-2 py-0.5 rounded">Episode</span>}
                      {task.scene_id && <span className="bg-gray-100 px-2 py-0.5 rounded">Scene</span>}
                      {task.google_account_id && <span className="bg-gray-100 px-2 py-0.5 rounded">Google Account</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    {task.status === 'pending' || task.status === 'in_progress' ? (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => startImport(task.id)}
                        disabled={importingId === task.id}
                        className="h-8 px-3 text-xs"
                      >
                        {importingId === task.id ? (
                          <Loader2 className="w-3 h-3 animate-spin" aria-hidden="true" />
                        ) : (
                          <>
                            <Upload className="w-3 h-3 mr-1" aria-hidden="true" />
                            Import
                          </>
                        )}
                      </Button>
                    ) : null}
                    {task.output_files && task.output_files.length > 0 && (
                      <button
                        className="p-2 text-gray-400 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                        aria-label="View output files"
                      >
                        <Eye className="w-4 h-4" aria-hidden="true" />
                      </button>
                    )}
                    <button
                      onClick={() => startEdit(task)}
                      className="p-2 text-gray-400 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                      aria-label="Edit task"
                    >
                      <Edit className="w-4 h-4" aria-hidden="true" />
                    </button>
                    <button
                      onClick={() => handleDelete(task.id)}
                      disabled={deletingId === task.id}
                      className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50"
                      aria-label="Delete task"
                    >
                      {deletingId === task.id ? (
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
        isOpen={showCreateModal || !!editingTask}
        onClose={() => { setShowCreateModal(false); setEditingTask(null); resetForm(); }}
        title={editingTask ? 'Edit Flow Task' : 'Create Flow Task'}
        size="xl"
      >
        <form onSubmit={editingTask ? handleUpdate : handleCreate} className="space-y-4 max-h-[85vh] overflow-y-auto pr-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Input
              label="Title"
              placeholder="Task title"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              required
            />
            <Select
              value={formData.task_type}
              onValueChange={(v) => setFormData({ ...formData, task_type: v as TaskType })}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select task type" />
              </SelectTrigger>
              <SelectContent>
                {TASK_TYPES.map(type => (
                  <SelectItem key={type} value={type}>{TASK_TYPE_LABELS[type]}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
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
          </div>
          <Select
            value={formData.google_account_id}
            onValueChange={(v) => setFormData({ ...formData, google_account_id: v })}
            placeholder="Select Google account (optional)"
          >
            <SelectTrigger>
              <SelectValue placeholder="Google Account" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">None</SelectItem>
              {googleAccounts.filter(a => a.status === 'connected').map(acc => (
                <SelectItem key={acc.id} value={acc.id}>{acc.email} ({acc.display_name || 'No name'})</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Textarea
            label="Description"
            placeholder="Task description..."
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            rows={3}
          />
          <Textarea
            label="Input Prompts (JSON array)"
            placeholder='[{"prompt_type": "video_generation", "prompt_text": "A cinematic scene..."}]'
            value={formData.input_prompts}
            onChange={(e) => setFormData({ ...formData, input_prompts: e.target.value })}
            rows={4}
            fontMono
          />
          <Textarea
            label="Reference Assets (JSON array of asset IDs)"
            placeholder='["asset-id-1", "asset-id-2"]'
            value={formData.reference_assets}
            onChange={(e) => setFormData({ ...formData, reference_assets: e.target.value })}
            rows={2}
            fontMono
          />
          <div className="flex justify-end gap-3 pt-4 border-t">
            <Button type="button" variant="outline" onClick={() => { setShowCreateModal(false); setEditingTask(null); resetForm(); }}>
              Cancel
            </Button>
            <Button type="submit" loading={saving}>
              <Loader2 className="w-4 h-4 mr-2" aria-hidden="true" />
              {editingTask ? 'Save Changes' : 'Create Task'}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Export Prompts Modal */}
      <Modal
        isOpen={exportModal}
        onClose={() => { setExportModal(false); setExportResult(null); }}
        title="Export Prompts for Flow"
        size="md"
      >
        <form onSubmit={handleExport} className="space-y-4">
          <p className="text-sm text-gray-600">
            Export all prompts from a project/episode/scene for manual Google Flow generation.
            The exported JSON can be used as reference in Google Flow.
          </p>
          <Select
            value={formData.episode_id}
            onValueChange={(v) => setFormData({ ...formData, episode_id: v })}
            placeholder="Select episode (optional)"
          >
            <SelectTrigger>
              <SelectValue placeholder="Episode (all episodes if empty)" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All Episodes</SelectItem>
              {episodes.map(ep => (
                <SelectItem key={ep.id} value={ep.id}>Episode {ep.episode_number}: {ep.title || 'Untitled'}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={formData.scene_id}
            onValueChange={(v) => setFormData({ ...formData, scene_id: v })}
            placeholder="Select scene (optional)"
          >
            <SelectTrigger>
              <SelectValue placeholder="Scene (all scenes in episode if empty)" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All Scenes</SelectItem>
              {Object.values(scenes).flat().map(scene => (
                <SelectItem key={scene.id} value={scene.id}>
                  Ep {scene.episode_id?.slice(-4)} - Scene {scene.scene_number}: {scene.title || 'Untitled'}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="flex justify-end gap-3 pt-4 border-t">
            <Button type="button" variant="outline" onClick={() => { setExportModal(false); setExportResult(null); }}>
              Cancel
            </Button>
            <Button type="submit" loading={exporting}>
              <Loader2 className="w-4 h-4 mr-2" aria-hidden="true" />
              Export & Download
            </Button>
          </div>
        </form>
      </Modal>

      {/* Import Results Modal */}
      {importModal && (
        <Modal
          isOpen={true}
          onClose={() => { setImportModal(null); setImportFiles('[]'); }}
          title="Import Flow Results"
          size="md"
        >
          <form onSubmit={(e) => { e.preventDefault(); handleImport(importModal!); }} className="space-y-4">
            <p className="text-sm text-gray-600">
              Paste the array of output file paths/URLs from Google Flow generation.
            </p>
            <Textarea
              label="Output Files (JSON array)"
              placeholder='["https://drive.google.com/file/...", "https://drive.google.com/file/..."]'
              value={importFiles}
              onChange={(e) => setImportFiles(e.target.value)}
              rows={4}
              fontMono
            />
            <div className="flex justify-end gap-3 pt-4 border-t">
              <Button type="button" variant="outline" onClick={() => { setImportModal(null); setImportFiles('[]'); }}>
                Cancel
              </Button>
              <Button type="submit" loading={importingId === importModal}>
                <Loader2 className="w-4 h-4 mr-2" aria-hidden="true" />
                Import Results
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}