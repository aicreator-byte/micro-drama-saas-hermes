'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useAuthStore } from '@/lib/auth-store';
import { useProjectStore } from '@/lib/project-store';
import { api } from '@/lib/api';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { formatDate, cn, getStatusColor } from '@/lib/utils';
import {
  FolderKanban,
  BookOpen,
  Users,
  MapPin,
  Film,
  Clapperboard,
  Bot,
  PlugZap,
  Plus,
  ArrowRight,
  LayoutDashboard,
} from 'lucide-react';

const quickActions = [
  { name: 'New Project', href: '/dashboard/projects/new', icon: Plus, description: 'Create a new drama project' },
  { name: 'Series Bible', href: '/dashboard/series-bible', icon: BookOpen, description: 'Define your story premise and structure' },
  { name: 'Characters', href: '/dashboard/characters', icon: Users, description: 'Create and manage characters' },
  { name: 'Locations', href: '/dashboard/locations', icon: MapPin, description: 'Set up shooting locations' },
  { name: 'Episodes', href: '/dashboard/episodes', icon: Film, description: 'Manage episode outlines' },
  { name: 'Scenes', href: '/dashboard/scenes', icon: Clapperboard, description: 'Break down scenes and shots' },
  { name: 'Prompts', href: '/dashboard/prompts', icon: Bot, description: 'Generate AI prompts' },
  { name: 'Flow Bridge', href: '/dashboard/flow', icon: PlugZap, description: 'Export for Google Flow' },
];

const navItems = [
  { name: 'Projects', href: '/dashboard/projects', icon: FolderKanban, count: 0 },
  { name: 'Series Bible', href: '/dashboard/series-bible', icon: BookOpen, count: 0 },
  { name: 'Characters', href: '/dashboard/characters', icon: Users, count: 0 },
  { name: 'Locations', href: '/dashboard/locations', icon: MapPin, count: 0 },
  { name: 'Episodes', href: '/dashboard/episodes', icon: Film, count: 0 },
  { name: 'Scenes', href: '/dashboard/scenes', icon: Clapperboard, count: 0 },
  { name: 'Prompts', href: '/dashboard/prompts', icon: Bot, count: 0 },
  { name: 'Flow Bridge', href: '/dashboard/flow', icon: PlugZap, count: 0 },
];

export default function DashboardPage() {
  const { user } = useAuthStore();
  const { currentProject, fetchProjects, projects, isLoading: projectsLoading } = useProjectStore();
  const [recentProjects, setRecentProjects] = useState<typeof projects>([]);
  const [stats, setStats] = useState({
    totalProjects: 0,
    totalCharacters: 0,
    totalEpisodes: 0,
    totalScenes: 0,
  });

  useEffect(() => {
    const loadData = async () => {
      try {
        const response = await api.listProjects(1, 10);
        setRecentProjects(response.items);
        setStats((prev) => ({ ...prev, totalProjects: response.total }));
      } catch {
        // Ignore errors for dashboard stats
      }
    };
    loadData();
  }, []);

  // This is a placeholder - in real app, we'd fetch actual counts
  useEffect(() => {
    if (currentProject) {
      // Could fetch project-specific stats here
    }
  }, [currentProject]);

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Welcome Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Welcome back, {user?.full_name?.split(' ')[0] || 'Creator'}!
          </h1>
          <p className="mt-1 text-gray-600">
            Continue building your micro drama series
          </p>
        </div>
        <Link href="/dashboard/projects/new">
          <Button size="lg">
            <Plus className="w-5 h-5 mr-2" aria-hidden="true" />
            New Project
          </Button>
        </Link>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Projects"
          value={stats.totalProjects}
          icon={FolderKanban}
          color="bg-purple-100 text-purple-600"
          href="/dashboard/projects"
        />
        <StatCard
          title="Characters"
          value={stats.totalCharacters}
          icon={Users}
          color="bg-blue-100 text-blue-600"
          href="/dashboard/characters"
        />
        <StatCard
          title="Episodes"
          value={stats.totalEpisodes}
          icon={Film}
          color="bg-green-100 text-green-600"
          href="/dashboard/episodes"
        />
        <StatCard
          title="Scenes"
          value={stats.totalScenes}
          icon={Clapperboard}
          color="bg-orange-100 text-orange-600"
          href="/dashboard/scenes"
        />
      </div>

      {/* Current Project */}
      {currentProject && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <LayoutDashboard className="w-5 h-5 text-purple-600" aria-hidden="true" />
                Current Project
              </CardTitle>
              <CardDescription>{currentProject.description || 'No description'}</CardDescription>
            </div>
            <Link href={`/dashboard/projects/${currentProject.id}`}>
              <Button variant="outline" size="sm">
                Open Project
                <ArrowRight className="w-4 h-4 ml-1" aria-hidden="true" />
              </Button>
            </Link>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              <Badge variant="purple">{currentProject.status.replace('_', ' ')}</Badge>
              {currentProject.genre && <Badge variant="info">{currentProject.genre}</Badge>}
              {currentProject.themes?.map((theme) => (
                <Badge key={theme} variant="default">{theme}</Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Quick Actions */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
          {quickActions.map((action) => {
            const Icon = action.icon;
            return (
              <Link
                key={action.name}
                href={action.href}
                className="group p-4 border border-gray-200 rounded-xl hover:border-purple-300 hover:bg-purple-50 transition-colors"
              >
                <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center text-purple-600 group-hover:bg-purple-600 group-hover:text-white transition-colors">
                  <Icon className="w-5 h-5" aria-hidden="true" />
                </div>
                <h3 className="mt-3 font-medium text-gray-900 group-hover:text-purple-600 transition-colors">
                  {action.name}
                </h3>
                <p className="mt-1 text-xs text-gray-500">{action.description}</p>
              </Link>
            );
          })}
        </div>
      </div>

      {/* Recent Projects */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Recent Projects</h2>
          <Link href="/dashboard/projects" className="text-sm text-purple-600 hover:text-purple-700 font-medium">
            View all
            <ArrowRight className="w-4 h-4 ml-1 inline" aria-hidden="true" />
          </Link>
        </div>
        {recentProjects.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <FolderKanban className="w-12 h-12 text-gray-300 mx-auto mb-4" aria-hidden="true" />
              <h3 className="text-lg font-medium text-gray-900 mb-1">No projects yet</h3>
              <p className="text-gray-500 mb-4">Create your first micro drama project to get started</p>
              <Link href="/dashboard/projects/new">
                <Button>
                  <Plus className="w-4 h-4 mr-2" aria-hidden="true" />
                  Create Project
                </Button>
              </Link>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {recentProjects.map((project) => (
              <Link
                key={project.id}
                href={`/dashboard/projects/${project.id}`}
                className="group block p-4 border border-gray-200 rounded-xl hover:border-purple-300 hover:bg-purple-50 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-gray-900 group-hover:text-purple-600 transition-colors truncate">
                      {project.title}
                    </h3>
                    <p className="mt-1 text-sm text-gray-500 truncate">
                      {project.description || 'No description'}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <Badge variant="purple" className="text-xs">
                        {project.status.replace('_', ' ')}
                      </Badge>
                      {project.genre && (
                        <Badge variant="info" className="text-xs">{project.genre}</Badge>
                      )}
                    </div>
                  </div>
                  <ArrowRight className="w-5 h-5 text-gray-400 group-hover:text-purple-600 transition-colors flex-shrink-0" aria-hidden="true" />
                </div>
                <div className="mt-3 pt-3 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500">
                  <span>Updated {formatDate(project.updated_at)}</span>
                  <span>{project.themes?.length || 0} themes</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Navigation Cards */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Explore</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.name}
                href={item.href}
                className="group p-5 border border-gray-200 rounded-xl hover:border-purple-300 hover:bg-purple-50 transition-colors"
              >
                <div className="w-12 h-12 bg-gray-100 rounded-lg flex items-center justify-center text-gray-600 group-hover:bg-purple-100 group-hover:text-purple-600 transition-colors">
                  <Icon className="w-6 h-6" aria-hidden="true" />
                </div>
                <h3 className="mt-3 font-medium text-gray-900">{item.name}</h3>
                {item.count > 0 && (
                  <span className="mt-1 inline-block px-2 py-0.5 text-xs bg-purple-100 text-purple-700 rounded-full">
                    {item.count}
                  </span>
                )}
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function StatCard({
  title,
  value,
  icon: Icon,
  color,
  href,
}: {
  title: string;
  value: number;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  href: string;
}) {
  return (
    <Link href={href} className="group block p-5 border border-gray-200 rounded-xl hover:border-purple-300 hover:bg-purple-50 transition-colors">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500">{title}</p>
          <p className="mt-1 text-3xl font-bold text-gray-900 group-hover:text-purple-600 transition-colors">
            {value}
          </p>
        </div>
        <div className={cn('w-12 h-12 rounded-lg flex items-center justify-center', color)}>
          <Icon className="w-6 h-6" aria-hidden="true" />
        </div>
      </div>
    </Link>
  );
}