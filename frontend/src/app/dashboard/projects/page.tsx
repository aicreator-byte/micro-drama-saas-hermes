'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useProjectStore } from '@/lib/project-store';
import { api } from '@/lib/api';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/Select';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { AutoGenerateModal } from '@/components/AutoGenerateModal';
import { formatDate, cn, getStatusColor } from '@/lib/utils';
import type { Project } from '@/types';
import { Plus, Search, Filter, MoreHorizontal, Edit, Trash2, FolderOpen, Sparkles } from 'lucide-react';

export default function ProjectsPage() {
  const { projects, fetchProjects, createProject, deleteProject, isLoading, currentProject, setCurrentProject } = useProjectStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newProjectData, setNewProjectData] = useState({ title: '', description: '', genre: '', themes: '' });
  const [creating, setCreating] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [autoGenProject, setAutoGenProject] = useState<Project | null>(null);

  useEffect(() => {
    loadProjects();
  }, [page, searchQuery, statusFilter]);

  const loadProjects = async () => {
    try {
      const response = await api.listProjects(page, 10, statusFilter || undefined);
      // Filter by search query client-side for now
      const filtered = searchQuery
        ? response.items.filter(
            (p: { title: string; description?: string | null }) =>
              p.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
              p.description?.toLowerCase().includes(searchQuery.toLowerCase())
          )
        : response.items;
      // Update store with filtered results (this is a workaround since we can't easily modify the store's projects)
      // In a real app, you'd add search to the API
    } catch (error) {
      console.error('Failed to load projects:', error);
    }
  };

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      const project = await createProject({
        title: newProjectData.title,
        description: newProjectData.description || undefined,
        genre: newProjectData.genre || undefined,
        themes: newProjectData.themes ? newProjectData.themes.split(',').map((t) => t.trim()) : undefined,
      });
      setShowCreateModal(false);
      setNewProjectData({ title: '', description: '', genre: '', themes: '' });
      // Refresh list
      window.location.reload();
    } catch (error) {
      console.error('Failed to create project:', error);
      alert('Failed to create project');
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteProject = async (projectId: string) => {
    if (!confirm('Are you sure you want to delete this project? This action cannot be undone.')) return;
    setDeletingId(projectId);
    try {
      await deleteProject(projectId);
      window.location.reload();
    } catch (error) {
      console.error('Failed to delete project:', error);
      alert('Failed to delete project');
    } finally {
      setDeletingId(null);
    }
  };

  // We need to fetch projects directly since the store doesn't have pagination
  const [projectList, setProjectList] = useState<typeof projects>([]);

  useEffect(() => {
    const fetch = async () => {
      try {
        const response = await api.listProjects(page, 10, statusFilter || undefined);
        setProjectList(response.items);
        setTotal(response.total);
        setTotalPages(response.total_pages);
      } catch (error) {
        console.error('Failed to fetch projects:', error);
      }
    };
    fetch();
  }, [page, statusFilter]);

  // Filter by search query
  const filteredProjects = searchQuery
    ? projectList.filter(
        (p: { title: string; description?: string | null }) =>
          p.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
          p.description?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : projectList;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
          <p className="mt-1 text-gray-600">Manage your micro drama projects</p>
        </div>
        <Button onClick={() => setShowCreateModal(true)}>
          <Plus className="w-4 h-4 mr-2" aria-hidden="true" />
          New Project
        </Button>
      </div>

      {/* Search and Filter */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" aria-hidden="true" />
          <Input
            placeholder="Search projects..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
        <div className="flex gap-2">
          <Select
            value={statusFilter}
            onValueChange={(v) => setStatusFilter(v)}
            placeholder="All Status"
          >
            <SelectTrigger className="w-48">
              <SelectValue placeholder="All Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All Status</SelectItem>
              <SelectItem value="draft">Draft</SelectItem>
              <SelectItem value="in_production">In Production</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="archived">Archived</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Projects Grid */}
      {filteredProjects.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center">
            <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <FolderOpen className="w-8 h-8 text-gray-400" aria-hidden="true" />
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-1">No projects found</h3>
            <p className="text-gray-500 mb-4">
              {searchQuery || statusFilter
                ? 'Try adjusting your search or filter'
                : 'Create your first micro drama project to get started'}
            </p>
            {!searchQuery && !statusFilter && (
              <Button onClick={() => setShowCreateModal(true)}>
                <Plus className="w-4 h-4 mr-2" aria-hidden="true" />
                Create Project
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {filteredProjects.map((project) => (
              <Card key={project.id} className="group hover:shadow-md transition-shadow">
                <CardContent className="p-5">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-semibold text-gray-900 truncate group-hover:text-purple-600 transition-colors">
                          {project.title}
                        </h3>
                        <Badge className={getStatusColor(project.status)}>
                          {project.status.replace('_', ' ')}
                        </Badge>
                      </div>
                      <p className="text-sm text-gray-500 truncate mb-2">
                        {project.description || 'No description'}
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {project.genre && <Badge variant="info" className="text-xs">{project.genre}</Badge>}
                        {project.themes?.slice(0, 3).map((theme: string) => (
                          <Badge key={theme} variant="default" className="text-xs">{theme}</Badge>
                        ))}
                        {project.themes && project.themes.length > 3 && (
                          <Badge variant="default" className="text-xs">+{project.themes.length - 3} more</Badge>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 ml-4 flex-shrink-0">
                      <button
                        onClick={() => setAutoGenProject(project)}
                        className="p-2 text-gray-400 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                        aria-label="Auto-Generate"
                        title="Auto-Generate"
                      >
                        <Sparkles className="w-5 h-5" aria-hidden="true" />
                      </button>
                      <Link
                        href={`/dashboard/projects/${project.id}`}
                        className="p-2 text-gray-400 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                        aria-label="Open project"
                      >
                        <FolderOpen className="w-5 h-5" aria-hidden="true" />
                      </Link>
                      <button
                        onClick={() => handleDeleteProject(project.id)}
                        disabled={deletingId === project.id}
                        className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50"
                        aria-label="Delete project"
                      >
                        {deletingId === project.id ? (
                          <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                        ) : (
                          <Trash2 className="w-5 h-5" aria-hidden="true" />
                        )}
                      </button>
                    </div>
                  </div>
                  <div className="mt-4 pt-4 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500">
                    <span>Updated {formatDate(project.updated_at)}</span>
                    <span>{project.themes?.length || 0} themes • {project.genre || 'No genre'}</span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                Previous
              </Button>
              <span className="text-sm text-gray-600">
                Page {page} of {totalPages} ({total} total)
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
              >
                Next
              </Button>
            </div>
          )}
        </>
      )}

      {/* Auto-Generate Modal */}
      <AutoGenerateModal
        isOpen={!!autoGenProject}
        project={autoGenProject}
        onClose={() => setAutoGenProject(null)}
        onCompleted={() => window.location.reload()}
      />

      {/* Create Project Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Create New Project"
        size="md"
      >
        <form onSubmit={handleCreateProject} className="space-y-4">
          <Input
            label="Project Title"
            placeholder="My Amazing Micro Drama"
            value={newProjectData.title}
            onChange={(e) => setNewProjectData({ ...newProjectData, title: e.target.value })}
            required
            error={!newProjectData.title && showCreateModal ? 'Title is required' : undefined}
          />
          <Textarea
            label="Description"
            placeholder="Brief description of your drama series..."
            value={newProjectData.description}
            onChange={(e) => setNewProjectData({ ...newProjectData, description: e.target.value })}
            rows={3}
          />
          <Input
            label="Genre"
            placeholder="Drama, Thriller, Romance, Comedy..."
            value={newProjectData.genre}
            onChange={(e) => setNewProjectData({ ...newProjectData, genre: e.target.value })}
          />
          <Input
            label="Themes (comma-separated)"
            placeholder="love, betrayal, redemption, family..."
            value={newProjectData.themes}
            onChange={(e) => setNewProjectData({ ...newProjectData, themes: e.target.value })}
            helperText="Separate themes with commas"
          />
          <div className="flex justify-end gap-3 pt-4">
            <Button type="button" variant="outline" onClick={() => setShowCreateModal(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={creating}>
              Create Project
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}