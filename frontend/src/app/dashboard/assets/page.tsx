'use client';

import { useEffect, useState } from 'react';
import { useProjectStore } from '@/lib/project-store';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/Select';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { formatDate, cn, formatFileSize } from '@/lib/utils';
import { Plus, Trash2, Download, Loader2, FileVideo, FileImage, FileAudio, FileText, File, Play, Music, Image, Scissors, Sparkles, ChevronDown, ChevronUp } from 'lucide-react';

const ASSET_TYPES = ['image', 'video', 'audio', 'subtitle', 'document'] as const;
type AssetType = typeof ASSET_TYPES[number];

const ASSET_TYPE_LABELS: Record<AssetType, string> = {
  image: 'Image',
  video: 'Video',
  audio: 'Audio',
  subtitle: 'Subtitle',
  document: 'Document',
};

const ASSET_TYPE_ICONS: Record<AssetType, React.ReactNode> = {
  image: <Image className="w-5 h-5" aria-hidden="true" />,
  video: <FileVideo className="w-5 h-5" aria-hidden="true" />,
  audio: <FileAudio className="w-5 h-5" aria-hidden="true" />,
  subtitle: <FileText className="w-5 h-5" aria-hidden="true" />,
  document: <File className="w-5 h-5" aria-hidden="true" />,
};

const ASSET_TYPE_COLORS: Record<AssetType, string> = {
  image: 'bg-blue-100 text-blue-800',
  video: 'bg-purple-100 text-purple-800',
  audio: 'bg-green-100 text-green-800',
  subtitle: 'bg-orange-100 text-orange-800',
  document: 'bg-gray-100 text-gray-800',
};

export default function AssetsPage() {
  const { currentProject, assets, fetchAssets, uploadAsset, deleteAsset, assembleEpisodeVideo, addSubtitlesToVideo, episodes, scenes } = useProjectStore();
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [assembleModal, setAssembleModal] = useState<string | null>(null);
  const [subtitleModal, setSubtitleModal] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<AssetType | 'all'>('all');
  const [filterEpisode, setFilterEpisode] = useState<string>('all');
  const [filterScene, setFilterScene] = useState<string>('all');
  const [uploadForm, setUploadForm] = useState({
    file: null as File | null,
    asset_type: 'image' as AssetType,
    episode_id: '',
    scene_id: '',
    metadata: '',
  });
  const [assembleForm, setAssembleForm] = useState({
    scene_order: '[]',
    output_filename: 'episode_final.mp4',
    include_audio: true,
    include_subtitles: false,
  });
  const [subtitleForm, setSubtitleForm] = useState({
    video_asset_id: '',
    subtitle_asset_id: '',
    output_filename: 'episode_with_subs.mp4',
  });
  const [uploading, setUploading] = useState(false);
  const [assemblingId, setAssemblingId] = useState<string | null>(null);
  const [subtitlingId, setSubtitlingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [assembleResult, setAssembleResult] = useState<any>(null);

  useEffect(() => {
    if (currentProject) {
      fetchAssets(currentProject.id, {
        asset_type: filterType === 'all' ? undefined : filterType,
        episode_id: filterEpisode === 'all' ? undefined : filterEpisode,
        scene_id: filterScene === 'all' ? undefined : filterScene,
      });
    }
  }, [currentProject, fetchAssets, filterType, filterEpisode, filterScene]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setUploadForm(prev => ({ ...prev, file }));
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentProject || !uploadForm.file) return;
    setUploading(true);
    try {
      const metadata = uploadForm.metadata ? JSON.parse(uploadForm.metadata) : undefined;
      await uploadAsset(
        currentProject.id,
        uploadForm.file,
        uploadForm.asset_type,
        uploadForm.episode_id || undefined,
        uploadForm.scene_id || undefined,
        metadata
      );
      setShowUploadModal(false);
      resetUploadForm();
    } catch (error) {
      console.error('Failed to upload asset:', error);
      alert('Failed to upload asset');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (assetId: string) => {
    if (!currentProject) return;
    if (!confirm('Are you sure you want to delete this asset?')) return;
    setDeletingId(assetId);
    try {
      await deleteAsset(currentProject.id, assetId);
    } catch (error) {
      console.error('Failed to delete asset:', error);
      alert('Failed to delete asset');
    } finally {
      setDeletingId(null);
    }
  };

  const handleAssemble = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentProject || !assembleModal) return;
    setAssemblingId(assembleModal);
    try {
      const sceneOrder = JSON.parse(assembleForm.scene_order);
      const result = await assembleEpisodeVideo(
        currentProject.id,
        assembleModal,
        sceneOrder,
        assembleForm.output_filename,
        assembleForm.include_audio,
        assembleForm.include_subtitles
      );
      setAssembleResult(result);
      alert(`Video assembled successfully! Asset ID: ${result.asset_id}`);
      setAssembleModal(null);
      setAssembleForm({
        scene_order: '[]',
        output_filename: 'episode_final.mp4',
        include_audio: true,
        include_subtitles: false,
      });
    } catch (error) {
      console.error('Failed to assemble video:', error);
      alert('Failed to assemble video');
    } finally {
      setAssemblingId(null);
    }
  };

  const handleAddSubtitles = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentProject || !subtitleModal) return;
    setSubtitlingId(subtitleModal);
    try {
      const result = await addSubtitlesToVideo(
        currentProject.id,
        subtitleModal,
        subtitleForm.video_asset_id,
        subtitleForm.subtitle_asset_id,
        subtitleForm.output_filename
      );
      alert(`Subtitles added successfully! Asset ID: ${result.asset_id}`);
      setSubtitleModal(null);
      setSubtitleForm({
        video_asset_id: '',
        subtitle_asset_id: '',
        output_filename: 'episode_with_subs.mp4',
      });
    } catch (error) {
      console.error('Failed to add subtitles:', error);
      alert('Failed to add subtitles');
    } finally {
      setSubtitlingId(null);
    }
  };

  const startAssemble = (episodeId: string) => {
    setAssembleModal(episodeId);
    // Pre-fill with scenes in order
    const epScenes = Object.values(scenes).flat().filter(s => s.episode_id === episodeId).sort((a, b) => a.scene_number - b.scene_number);
    if (epScenes.length > 0) {
      setAssembleForm(prev => ({
        ...prev,
        scene_order: JSON.stringify(epScenes.map(s => s.id), null, 2),
        output_filename: `episode-${epScenes[0]?.episode_id?.slice(-4) || 'final'}.mp4`,
      }));
    }
  };

  const startSubtitles = (episodeId: string) => {
    setSubtitleModal(episodeId);
    // Pre-fill with available video and subtitle assets
    const videoAssets = assets.filter(a => a.asset_type === 'video' && a.episode_id === episodeId);
    const subtitleAssets = assets.filter(a => a.asset_type === 'subtitle' && a.episode_id === episodeId);
    if (videoAssets.length > 0) {
      setSubtitleForm(prev => ({ ...prev, video_asset_id: videoAssets[0].id }));
    }
    if (subtitleAssets.length > 0) {
      setSubtitleForm(prev => ({ ...prev, subtitle_asset_id: subtitleAssets[0].id }));
    }
  };

  const resetUploadForm = () => {
    setUploadForm({
      file: null,
      asset_type: 'image',
      episode_id: '',
      scene_id: '',
      metadata: '',
    });
  };

  const filteredAssets = assets.filter(asset => {
    const typeMatch = filterType === 'all' || asset.asset_type === filterType;
    const epMatch = filterEpisode === 'all' || asset.episode_id === filterEpisode;
    const sceneMatch = filterScene === 'all' || asset.scene_id === filterScene;
    return typeMatch && epMatch && sceneMatch;
  });

  if (!currentProject) {
    return (
      <div className="text-center py-16">
        <FileVideo className="w-16 h-16 text-gray-300 mx-auto mb-4" aria-hidden="true" />
        <h2 className="text-xl font-semibold text-gray-900 mb-2">No project selected</h2>
        <p className="text-gray-500 mb-4">Select a project from the dashboard to manage assets</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Asset Manager</h1>
          <p className="text-gray-600">Upload, organize, and process production assets. Assemble episodes with FFmpeg.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={() => { resetUploadForm(); setShowUploadModal(true); }}>
            <Plus className="w-4 h-4 mr-2" aria-hidden="true" />
            Upload Asset
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <Select value={filterType} onValueChange={setFilterType as any}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="All types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            {ASSET_TYPES.map(type => (
              <SelectItem key={type} value={type}>{ASSET_TYPE_LABELS[type]}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={filterEpisode} onValueChange={setFilterEpisode}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="All episodes" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Episodes</SelectItem>
            {episodes.map(ep => (
              <SelectItem key={ep.id} value={ep.id}>Episode {ep.episode_number}: {ep.title || 'Untitled'}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={filterScene} onValueChange={setFilterScene}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="All scenes" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Scenes</SelectItem>
            {Object.values(scenes).flat().map(scene => (
              <SelectItem key={scene.id} value={scene.id}>
                Ep {scene.episode_id?.slice(-4)} - Scene {scene.scene_number}: {scene.title || 'Untitled'}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="text-sm text-gray-500">{filteredAssets.length} of {assets.length} assets</span>
      </div>

      {/* Episode Assembly Actions */}
      {episodes.length > 0 && (
        <Card className="bg-purple-50 border-purple-200">
          <CardContent className="pt-4">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h3 className="font-semibold text-purple-900">Episode Assembly</h3>
                <p className="text-sm text-purple-700">Assemble final episode videos from scene assets using FFmpeg</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {episodes.map(ep => (
                  <Button key={ep.id} variant="outline" size="sm" onClick={() => startAssemble(ep.id)} disabled={assemblingId === ep.id}>
                    {assemblingId === ep.id ? (
                      <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
                    ) : (
                      <>
                        <Sparkles className="w-3 h-3 mr-1" aria-hidden="true" />
                        Ep {ep.episode_number}
                      </>
                    )}
                  </Button>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {filteredAssets.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center">
            <FileVideo className="w-16 h-16 text-gray-300 mx-auto mb-4" aria-hidden="true" />
            <h3 className="text-lg font-medium text-gray-900 mb-1">No assets yet</h3>
            <p className="text-gray-500 mb-4">Upload images, videos, audio, subtitles, or documents for your production</p>
            <Button onClick={() => { resetUploadForm(); setShowUploadModal(true); }}>
              <Plus className="w-4 h-4 mr-2" aria-hidden="true" />
              Upload Asset
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filteredAssets.map((asset) => (
            <Card
              key={asset.id}
              className="group relative"
            >
              <CardContent className="p-3">
                <div className="aspect-video bg-gray-100 rounded-lg mb-3 flex items-center justify-center overflow-hidden relative">
                  {asset.asset_type === 'image' && asset.file_path && (
                    <img
                      src={asset.file_path.startsWith('http') ? asset.file_path : `/api/assets/${currentProject.id}/${asset.id}/download`}
                      alt={asset.file_name}
                      className="max-w-full max-h-full object-contain"
                    />
                  )}
                  {asset.asset_type === 'video' && (
                    <div className="text-center">
                      <FileVideo className="w-12 h-12 text-purple-500 mx-auto mb-2" aria-hidden="true" />
                      <p className="text-xs text-gray-500">Video Asset</p>
                    </div>
                  )}
                  {asset.asset_type === 'audio' && (
                    <div className="text-center">
                      <Music className="w-12 h-12 text-green-500 mx-auto mb-2" aria-hidden="true" />
                      <p className="text-xs text-gray-500">Audio Asset</p>
                    </div>
                  )}
                  {asset.asset_type === 'subtitle' && (
                    <div className="text-center">
                      <FileText className="w-12 h-12 text-orange-500 mx-auto mb-2" aria-hidden="true" />
                      <p className="text-xs text-gray-500">Subtitle Asset</p>
                    </div>
                  )}
                  {asset.asset_type === 'document' && (
                    <div className="text-center">
                      <File className="w-12 h-12 text-gray-500 mx-auto mb-2" aria-hidden="true" />
                      <p className="text-xs text-gray-500">Document</p>
                    </div>
                  )}
                  <div className="absolute top-2 right-2">
                    <Badge variant="purple" className={cn('text-xs', ASSET_TYPE_COLORS[asset.asset_type])}>
                      {ASSET_TYPE_ICONS[asset.asset_type]}
                      {ASSET_TYPE_LABELS[asset.asset_type]}
                    </Badge>
                  </div>
                </div>
                <h4 className="font-medium text-gray-900 text-sm truncate mb-1" title={asset.file_name}>
                  {asset.file_name}
                </h4>
                <div className="flex items-center justify-between text-xs text-gray-500">
                  <span>{asset.file_size ? formatFileSize(asset.file_size) : 'Unknown size'}</span>
                  <span>{formatDate(asset.created_at)}</span>
                </div>
                {asset.episode_id && (
                  <span className="inline-block mt-1 px-1.5 py-0.5 bg-gray-100 text-gray-700 rounded text-xs">
                    Episode
                  </span>
                )}
                {asset.scene_id && (
                  <span className="inline-block mt-1 px-1.5 py-0.5 bg-gray-100 text-gray-700 rounded text-xs ml-1">
                    Scene
                  </span>
                )}
                <div className="flex items-center gap-1 mt-2">
                  {asset.asset_type === 'video' && (
                    <button
                      className="flex-1 p-1.5 text-xs text-gray-600 hover:text-purple-600 hover:bg-purple-50 rounded transition-colors"
                      aria-label="Play video"
                    >
                      <Play className="w-3 h-3 mr-1" aria-hidden="true" />
                      Preview
                    </button>
                  )}
                  <button
                    className="flex-1 p-1.5 text-xs text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
                    aria-label="Download asset"
                  >
                    <Download className="w-3 h-3 mx-auto" aria-hidden="true" />
                  </button>
                  <button
                    onClick={() => handleDelete(asset.id)}
                    disabled={deletingId === asset.id}
                    className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors disabled:opacity-50"
                    aria-label="Delete asset"
                  >
                    {deletingId === asset.id ? (
                      <Loader2 className="w-3 h-3 animate-spin" aria-hidden="true" />
                    ) : (
                      <Trash2 className="w-3 h-3" aria-hidden="true" />
                    )}
                  </button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Upload Modal */}
      <Modal
        isOpen={showUploadModal}
        onClose={() => { setShowUploadModal(false); resetUploadForm(); }}
        title="Upload Asset"
        size="md"
      >
        <form onSubmit={handleUpload} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">File</label>
            <input
              type="file"
              onChange={handleFileChange}
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
              accept="image/*,video/*,audio/*,text/*,.srt,.vtt,.pdf"
            />
          </div>
          <Select
            value={uploadForm.asset_type}
            onValueChange={(v) => setUploadForm({ ...uploadForm, asset_type: v as AssetType })}
          >
            <SelectTrigger>
              <SelectValue placeholder="Select asset type" />
            </SelectTrigger>
            <SelectContent>
              {ASSET_TYPES.map(type => (
                <SelectItem key={type} value={type}>
                  {ASSET_TYPE_ICONS[type]}
                  {ASSET_TYPE_LABELS[type]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={uploadForm.episode_id}
            onValueChange={(v) => setUploadForm({ ...uploadForm, episode_id: v })}
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
            value={uploadForm.scene_id}
            onValueChange={(v) => setUploadForm({ ...uploadForm, scene_id: v })}
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
          <Textarea
            label="Metadata (JSON, optional)"
            placeholder='{"width": 1920, "height": 1080, "duration": 30}'
            value={uploadForm.metadata}
            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setUploadForm({ ...uploadForm, metadata: e.target.value })}
            rows={3}
            fontMono
          />
          <div className="flex justify-end gap-3 pt-4 border-t">
            <Button type="button" variant="outline" onClick={() => { setShowUploadModal(false); resetUploadForm(); }}>
              Cancel
            </Button>
            <Button type="submit" loading={uploading} disabled={!uploadForm.file}>
              <Loader2 className="w-4 h-4 mr-2" aria-hidden="true" />
              Upload
            </Button>
          </div>
        </form>
      </Modal>

      {/* Assemble Episode Modal */}
      {assembleModal && (
        <Modal
          isOpen={true}
          onClose={() => { setAssembleModal(null); setAssembleResult(null); }}
          title="Assemble Episode Video"
          size="lg"
        >
          <form onSubmit={handleAssemble} className="space-y-4 max-h-[80vh] overflow-y-auto pr-4">
            <p className="text-sm text-gray-600">
              Specify the order of scene video assets to assemble into a final episode video using FFmpeg.
            </p>
            <Textarea
              label="Scene Order (JSON array of scene IDs)"
              placeholder='["scene-id-1", "scene-id-2", "scene-id-3"]'
              value={assembleForm.scene_order}
              onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setAssembleForm({ ...assembleForm, scene_order: e.target.value })}
              rows={4}
              fontMono
              required
            />
            <div className="grid gap-4 md:grid-cols-2">
              <Input
                label="Output Filename"
                placeholder="episode_final.mp4"
                value={assembleForm.output_filename}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setAssembleForm({ ...assembleForm, output_filename: e.target.value })}
              />
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={assembleForm.include_audio}
                  onChange={(e) => setAssembleForm({ ...assembleForm, include_audio: e.target.checked })}
                  className="rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                />
                <span className="text-sm text-gray-700">Include audio tracks</span>
              </label>
            </div>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={assembleForm.include_subtitles}
                onChange={(e) => setAssembleForm({ ...assembleForm, include_subtitles: e.target.checked })}
                className="rounded border-gray-300 text-purple-600 focus:ring-purple-500"
              />
              <span className="text-sm text-gray-700">Include subtitles (requires subtitle assets in scenes)</span>
            </label>
            {assembleResult && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                <h4 className="font-medium text-green-900 mb-1">Assembly Complete</h4>
                <p className="text-sm text-green-700">Asset ID: {assembleResult.asset_id}</p>
                <p className="text-sm text-green-700">File: {assembleResult.file_path}</p>
                <p className="text-sm text-green-700">Size: {formatFileSize(assembleResult.file_size)}</p>
              </div>
            )}
            <div className="flex justify-end gap-3 pt-4 border-t">
              <Button type="button" variant="outline" onClick={() => { setAssembleModal(null); setAssembleResult(null); }}>
                Cancel
              </Button>
              <Button type="submit" loading={assemblingId === assembleModal}>
                <Loader2 className="w-4 h-4 mr-2" aria-hidden="true" />
                Assemble Video
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {/* Add Subtitles Modal */}
      {subtitleModal && (
        <Modal
          isOpen={true}
          onClose={() => { setSubtitleModal(null); }}
          title="Add Subtitles to Video"
          size="md"
        >
          <form onSubmit={handleAddSubtitles} className="space-y-4">
            <p className="text-sm text-gray-600">
              Burn subtitles into a video asset using FFmpeg.
            </p>
            <Select
              value={subtitleForm.video_asset_id}
              onValueChange={(v) => setSubtitleForm({ ...subtitleForm, video_asset_id: v })}
              placeholder="Select video asset"
            >
              <SelectTrigger>
                <SelectValue placeholder="Video Asset" />
              </SelectTrigger>
              <SelectContent>
                {assets.filter(a => a.asset_type === 'video' && a.episode_id === subtitleModal).map(asset => (
                  <SelectItem key={asset.id} value={asset.id}>{asset.file_name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={subtitleForm.subtitle_asset_id}
              onValueChange={(v) => setSubtitleForm({ ...subtitleForm, subtitle_asset_id: v })}
              placeholder="Select subtitle asset"
            >
              <SelectTrigger>
                <SelectValue placeholder="Subtitle Asset" />
              </SelectTrigger>
              <SelectContent>
                {assets.filter(a => a.asset_type === 'subtitle' && a.episode_id === subtitleModal).map(asset => (
                  <SelectItem key={asset.id} value={asset.id}>{asset.file_name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              label="Output Filename"
              placeholder="episode_with_subs.mp4"
              value={subtitleForm.output_filename}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSubtitleForm({ ...subtitleForm, output_filename: e.target.value })}
            />
            <div className="flex justify-end gap-3 pt-4 border-t">
              <Button type="button" variant="outline" onClick={() => { setSubtitleModal(null); }}>
                Cancel
              </Button>
              <Button type="submit" loading={subtitlingId === subtitleModal} disabled={!subtitleForm.video_asset_id || !subtitleForm.subtitle_asset_id}>
                <Loader2 className="w-4 h-4 mr-2" aria-hidden="true" />
                Add Subtitles
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}