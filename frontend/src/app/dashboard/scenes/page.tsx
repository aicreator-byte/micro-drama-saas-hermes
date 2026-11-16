'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useProjectStore } from '@/lib/project-store';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { NativeSelect } from '@/components/ui/Select';
import { Badge } from '@/components/ui/Badge';
import { formatDate, getStatusColor } from '@/lib/utils';
import { Clapperboard, Plus, Edit, Trash2, ArrowRight, Sparkles, Loader2, Eye } from 'lucide-react';

export default function ScenesPage() {
  const { currentProject, episodes, scenes, fetchScenes, fetchEpisodes } = useProjectStore();
  const [selectedEpisodeId, setSelectedEpisodeId] = useState<string | null>(null);

  useEffect(() => {
    if (currentProject) {
      fetchEpisodes(currentProject.id);
    }
  }, [currentProject, fetchEpisodes]);

  useEffect(() => {
    if (selectedEpisodeId && currentProject) {
      fetchScenes(currentProject.id, selectedEpisodeId);
    }
  }, [selectedEpisodeId, currentProject, fetchScenes]);

  const episodeScenes = selectedEpisodeId ? scenes[selectedEpisodeId] || [] : [];

  if (!currentProject) {
    return (
      <div className="text-center py-16">
        <Clapperboard className="w-16 h-16 text-gray-300 mx-auto mb-4" aria-hidden="true" />
        <h2 className="text-xl font-semibold text-gray-900 mb-2">No project selected</h2>
        <p className="text-gray-500 mb-4">Select a project from the dashboard to manage scenes</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Scenes</h1>
          <p className="text-gray-600">Break down episodes into scenes with shot lists and camera directions</p>
        </div>
      </div>

      {/* Episode Selector */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-4">
            <NativeSelect
              label="Select Episode"
              value={selectedEpisodeId || ''}
              onChange={(e) => setSelectedEpisodeId(e.target.value || null)}
              placeholder="Choose an episode..."
              options={episodes.map((ep) => ({ value: ep.id, label: `Ep ${ep.episode_number}: ${ep.title || 'Untitled'}` }))}
            />
            {selectedEpisodeId && (
              <Button variant="outline">
                <Plus className="w-4 h-4 mr-2" aria-hidden="true" />
                Add Scene
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {selectedEpisodeId ? (
        episodeScenes.length === 0 ? (
          <Card>
            <CardContent className="py-16 text-center">
              <Clapperboard className="w-16 h-16 text-gray-300 mx-auto mb-4" aria-hidden="true" />
              <h3 className="text-lg font-medium text-gray-900 mb-1">No scenes yet</h3>
              <p className="text-gray-500 mb-4">Add scenes to this episode</p>
              <Button variant="outline">
                <Plus className="w-4 h-4 mr-2" aria-hidden="true" />
                Add Scene
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-4">
            {episodeScenes.map((scene) => (
              <Card key={scene.id} className="group">
                <CardContent className="p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center text-blue-600 font-semibold text-sm">
                          {scene.scene_number}
                        </span>
                        <h3 className="font-semibold text-gray-900">{scene.title || `Scene ${scene.scene_number}`}</h3>
                        <Badge className={getStatusColor(scene.status)}>
                          {scene.status.replace('_', ' ')}
                        </Badge>
                      </div>
                      <p className="mt-1 text-sm text-gray-500 line-clamp-2">
                        {scene.description || 'No description'}
                      </p>
                      <div className="mt-2 flex flex-wrap gap-2 text-xs text-gray-500">
                        {scene.camera_directions && <span>Camera: {scene.camera_directions.slice(0, 50)}...</span>}
                        <span>Updated {formatDate(scene.updated_at)}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 ml-4">
                      <Link href={`/dashboard/scenes/${selectedEpisodeId}/${scene.id}`}>
                        <button className="p-2 text-gray-400 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition-colors" aria-label="View scene">
                          <Eye className="w-4 h-4" aria-hidden="true" />
                        </button>
                      </Link>
                      <button className="p-2 text-gray-400 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition-colors" aria-label="Edit scene">
                        <Edit className="w-4 h-4" aria-hidden="true" />
                      </button>
                      <button className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors" aria-label="Delete scene">
                        <Trash2 className="w-4 h-4" aria-hidden="true" />
                      </button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )
      ) : (
        <Card>
          <CardContent className="py-16 text-center">
            <Clapperboard className="w-16 h-16 text-gray-300 mx-auto mb-4" aria-hidden="true" />
            <h3 className="text-lg font-medium text-gray-900 mb-1">Select an episode</h3>
            <p className="text-gray-500">Choose an episode above to view and manage its scenes</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}