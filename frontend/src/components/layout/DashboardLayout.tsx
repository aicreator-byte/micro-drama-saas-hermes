'use client';

import { ReactNode, useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuthStore } from '@/lib/auth-store';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  FolderKanban,
  BookOpen,
  Users,
  MapPin,
  Film,
  Clapperboard,
  MessageSquare,
  Bot,
  PlugZap,
  Settings,
  LogOut,
  Menu,
  X,
  ChevronDown,
  User,
  FileVideo,
  FileText,
  Sparkles,
} from 'lucide-react';

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Projects', href: '/dashboard/projects', icon: FolderKanban },
  { name: 'Series Bible', href: '/dashboard/series-bible', icon: BookOpen },
  { name: 'Characters', href: '/dashboard/characters', icon: Users },
  { name: 'Locations', href: '/dashboard/locations', icon: MapPin },
  { name: 'Episodes', href: '/dashboard/episodes', icon: Film },
  { name: 'Scenes', href: '/dashboard/scenes', icon: Clapperboard },
  { name: 'Dialogues', href: '/dashboard/dialogues', icon: MessageSquare },
  { name: 'Prompts', href: '/dashboard/prompts', icon: Sparkles },
  { name: 'Flow Bridge', href: '/dashboard/flow', icon: PlugZap },
  { name: 'Billing', href: '/dashboard/billing', icon: FileText },
  { name: 'Assets', href: '/dashboard/assets', icon: FileVideo },
  { name: 'Google Accounts', href: '/dashboard/google-accounts', icon: FileText },
  { name: 'Settings', href: '/dashboard/settings', icon: Settings },
];

export function DashboardLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuthStore();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (!target.closest('[data-user-menu]')) {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = () => {
    logout();
    api.logout();
    window.location.href = '/auth/login';
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 w-64 bg-white border-r border-gray-200 transform transition-transform duration-200 lg:translate-x-0',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
        aria-label="Sidebar"
      >
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="flex items-center h-16 px-6 border-b border-gray-200">
            <Link href="/dashboard" className="flex items-center gap-2">
              <div className="w-8 h-8 bg-gradient-to-br from-purple-600 to-blue-600 rounded-lg flex items-center justify-center">
                <Clapperboard className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-bold text-gray-900">Micro Drama SaaS</span>
            </Link>
          </div>

          {/* Navigation */}
          <nav className="flex-1 px-4 py-4 space-y-1 overflow-y-auto" role="navigation" aria-label="Main navigation">
            {navigation.map((item) => {
              const isActive = pathname === item.href || (item.href !== '/dashboard' && pathname.startsWith(item.href));
              const Icon = item.icon;
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={cn(
                    'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-purple-50 text-purple-700'
                      : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                  )}
                  aria-current={isActive ? 'page' : undefined}
                >
                  <Icon className="w-5 h-5 flex-shrink-0" aria-hidden="true" />
                  {item.name}
                </Link>
              );
            })}
          </nav>

          {/* User info */}
          <div className="p-4 border-t border-gray-200">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-gradient-to-br from-purple-600 to-blue-600 rounded-full flex items-center justify-center text-white font-medium">
                {user?.full_name?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'U'}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">{user?.full_name || 'User'}</p>
                <p className="text-xs text-gray-500 truncate">{user?.email}</p>
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="lg:pl-64">
        {/* Top header */}
        <header className="sticky top-0 z-30 bg-white border-b border-gray-200">
          <div className="flex items-center justify-between h-16 px-4 sm:px-6 lg:px-8">
            {/* Mobile menu button */}
            <button
              type="button"
              className="lg:hidden p-2 -ml-2 rounded-md text-gray-600 hover:text-gray-900 hover:bg-gray-100"
              onClick={() => setSidebarOpen(true)}
              aria-label="Open sidebar"
              aria-expanded={sidebarOpen}
            >
              <Menu className="w-6 h-6" aria-hidden="true" />
            </button>

            {/* Page title */}
            <h1 className="text-lg font-semibold text-gray-900 lg:hidden">
              {navigation.find((item) => pathname === item.href || (item.href !== '/dashboard' && pathname.startsWith(item.href)))?.name || 'Dashboard'}
            </h1>

            {/* User menu */}
            <div className="relative" data-user-menu>
              <button
                type="button"
                className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-purple-500"
                onClick={() => setUserMenuOpen(!userMenuOpen)}
                aria-expanded={userMenuOpen}
                aria-haspopup="true"
              >
                <div className="w-8 h-8 bg-gradient-to-br from-purple-600 to-blue-600 rounded-full flex items-center justify-center text-white font-medium">
                  {user?.full_name?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'U'}
                </div>
                <ChevronDown className="w-4 h-4 text-gray-500 hidden sm:block" aria-hidden="true" />
              </button>

              {userMenuOpen && (
                <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-50">
                  <div className="px-4 py-2 border-b border-gray-100">
                    <p className="text-sm font-medium text-gray-900 truncate">{user?.full_name || 'User'}</p>
                    <p className="text-xs text-gray-500 truncate">{user?.email}</p>
                  </div>
                  <Link
                    href="/settings"
                    className="flex items-center gap-2 px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                    onClick={() => setUserMenuOpen(false)}
                  >
                    <User className="w-4 h-4" aria-hidden="true" />
                    Profile
                  </Link>
                  <Link
                    href="/settings"
                    className="flex items-center gap-2 px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                    onClick={() => setUserMenuOpen(false)}
                  >
                    <Settings className="w-4 h-4" aria-hidden="true" />
                    Settings
                  </Link>
                  <hr className="my-1 border-gray-100" />
                  <button
                    type="button"
                    className="flex items-center gap-2 w-full px-4 py-2 text-sm text-red-600 hover:bg-gray-100"
                    onClick={handleLogout}
                  >
                    <LogOut className="w-4 h-4" aria-hidden="true" />
                    Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="p-4 sm:p-6 lg:p-8" role="main">
          {children}
        </main>
      </div>
    </div>
  );
}