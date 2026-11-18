'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { cn } from '@/lib/utils';
import {
  Settings,
  Sparkles,
  Shield,
  Key,
  ChevronUp,
  ChevronDown,
  Save,
  Loader2,
  CheckCircle,
  AlertCircle,
  Eye,
  EyeOff,
  Plus,
  Trash2,
  Globe,
  Cpu,
  Bot,
  Info,
  HelpCircle,
} from 'lucide-react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/Select';

const PROVIDER_ICONS: Record<string, React.ReactNode> = {
  nvidia: <Cpu className="w-5 h-5" aria-hidden="true" />,
  openai: <Globe className="w-5 h-5" aria-hidden="true" />,
  default: <Sparkles className="w-5 h-5" aria-hidden="true" />,
};

interface ProviderConfig {
  id?: string;
  name: string;
  provider?: string;
  model: string;
  api_key_env: string;
  base_url?: string;
  enabled: boolean;
  order: number;
  priority?: number;
}

interface AppSettingsResponse {
  ai_providers: ProviderConfig[];
  google_oauth_client_id_configured: boolean;
  google_oauth_client_secret_configured: boolean;
}

interface AppSettingsUpdate {
  ai_providers?: ProviderConfig[];
  google_oauth_client_id?: string;
  google_oauth_client_secret?: string;
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showOAuthModal, setShowOAuthModal] = useState(false);
  const [oauthClientId, setOauthClientId] = useState('');
  const [oauthClientSecret, setOauthClientSecret] = useState('');
  const [showClientId, setShowClientId] = useState(false);
  const [showClientSecret, setShowClientSecret] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const data = await api.getSettings();
      // Sort providers by order
      const sortedProviders = [...data.ai_providers].sort((a, b) => a.order - b.order);
      setSettings({ ...data, ai_providers: sortedProviders });
    } catch (error) {
      console.error('Failed to fetch settings:', error);
      setMessage({ type: 'error', text: 'Failed to load settings' });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!settings) return;
    setSaving(true);
    try {
      await api.updateSettings({
        ai_providers: settings.ai_providers,
      });
      setMessage({ type: 'success', text: 'Settings saved successfully' });
      setTimeout(() => setMessage(null), 3000);
    } catch (error: any) {
      console.error('Failed to save settings:', error);
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Failed to save settings' });
    } finally {
      setSaving(false);
    }
  };

  const handleSaveOAuth = async () => {
    setSaving(true);
    try {
      await api.updateSettings({
        google_oauth_client_id: oauthClientId,
        google_oauth_client_secret: oauthClientSecret,
      });
      setShowOAuthModal(false);
      setOauthClientId('');
      setOauthClientSecret('');
      await fetchSettings();
      setMessage({ type: 'success', text: 'OAuth credentials saved successfully' });
      setTimeout(() => setMessage(null), 3000);
    } catch (error: any) {
      console.error('Failed to save OAuth credentials:', error);
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Failed to save OAuth credentials' });
    } finally {
      setSaving(false);
    }
  };

  const moveProvider = (index: number, direction: 'up' | 'down') => {
    if (!settings) return;
    const newProviders = [...settings.ai_providers];
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= newProviders.length) return;

    [newProviders[index], newProviders[targetIndex]] = [newProviders[targetIndex], newProviders[index]];
    // Update order values
    newProviders.forEach((p, i) => { p.order = i; });
    setSettings({ ...settings, ai_providers: newProviders });
  };

  const toggleProvider = (index: number) => {
    if (!settings) return;
    const newProviders = [...settings.ai_providers];
    newProviders[index] = { ...newProviders[index], enabled: !newProviders[index].enabled };
    setSettings({ ...settings, ai_providers: newProviders });
  };

  const addProvider = () => {
    if (!settings) return;
    const newProvider: ProviderConfig = {
      name: '',
      model: '',
      api_key_env: '',
      base_url: '',
      enabled: true,
      order: settings.ai_providers.length,
    };
    setSettings({ ...settings, ai_providers: [...settings.ai_providers, newProvider] });
  };

  const removeProvider = (index: number) => {
    if (!settings || settings.ai_providers.length <= 1) return;
    const newProviders = settings.ai_providers.filter((_, i) => i !== index);
    newProviders.forEach((p, i) => { p.order = i; });
    setSettings({ ...settings, ai_providers: newProviders });
  };

  const updateProviderField = (index: number, field: keyof ProviderConfig, value: string | boolean) => {
    if (!settings) return;
    const newProviders = settings.ai_providers.map((p, i) =>
      i === index ? { ...p, [field]: value } : p
    );
    setSettings({ ...settings, ai_providers: newProviders });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-purple-600" aria-hidden="true" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Settings className="w-6 h-6 text-purple-600" aria-hidden="true" />
            Settings
          </h1>
          <p className="text-gray-600 mt-1">Configure AI providers, fallback order, and Google OAuth credentials</p>
        </div>
        <Button onClick={handleSave} loading={saving} disabled={!settings}>
          <Save className="w-4 h-4 mr-2" aria-hidden="true" />
          Save Settings
        </Button>
      </div>

      {message && (
        <div className={cn(
          'p-4 rounded-lg flex items-center gap-3 animate-slide-in',
          message.type === 'success' ? 'bg-green-50 text-green-800 border border-green-200' : 'bg-red-50 text-red-800 border border-red-200'
        )}>
          {message.type === 'success' ? (
            <CheckCircle className="w-5 h-5 flex-shrink-0" aria-hidden="true" />
          ) : (
            <AlertCircle className="w-5 h-5 flex-shrink-0" aria-hidden="true" />
          )}
          <span>{message.text}</span>
        </div>
      )}

      {/* AI Providers Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Bot className="w-5 h-5 text-purple-600" aria-hidden="true" />
                AI Providers & Fallback Order
              </CardTitle>
              <CardDescription>
                Drag to reorder (fallback priority). Only enabled providers will be used.
                First provider in the list is tried first, then falls back to next on failure.
                <span className="relative inline-block ml-2" title="API keys are read from environment variables, not stored in the database.">
                  <Info className="w-4 h-4 inline text-gray-400" aria-hidden="true" />
                </span>
              </CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={addProvider}>
              <Plus className="w-4 h-4 mr-2" aria-hidden="true" />
              Add Provider
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {settings?.ai_providers.map((provider, index) => (
            <div
              key={`${provider.name}-${index}`}
              className={cn(
                'border rounded-xl p-4 transition-colors',
                provider.enabled ? 'bg-white border-gray-200' : 'bg-gray-50 border-gray-100 opacity-75'
              )}
            >
              <div className="flex items-start gap-4">
                {/* Move buttons */}
                <div className="flex flex-col items-center text-gray-400 pt-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => moveProvider(index, 'up')}
                    disabled={index === 0}
                    aria-label="Move up"
                    className="p-1 h-8 w-8"
                  >
                    <ChevronUp className="w-4 h-4" aria-hidden="true" />
                  </Button>
                  <span className="text-sm font-mono text-gray-500 w-6 text-center">{index + 1}</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => moveProvider(index, 'down')}
                    disabled={index === settings.ai_providers.length - 1}
                    aria-label="Move down"
                    className="p-1 h-8 w-8"
                  >
                    <ChevronDown className="w-4 h-4" aria-hidden="true" />
                  </Button>
                </div>

                {/* Provider details */}
                <div className="flex-1 min-w-0 grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">Provider Name</label>
                    <Input
                      placeholder="e.g., Nvidia NIM"
                      value={provider.name}
                      onChange={(e) => updateProviderField(index, 'name', e.target.value)}
                      className="font-mono text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">Model</label>
                    <Input
                      placeholder="e.g., nemotron-3-ultra-550b"
                      value={provider.model}
                      onChange={(e) => updateProviderField(index, 'model', e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">API Key Env Var</label>
                    <Input
                      placeholder="e.g., NVIDIA_API_KEY"
                      value={provider.api_key_env}
                      onChange={(e) => updateProviderField(index, 'api_key_env', e.target.value)}
                      className="font-mono text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">Base URL (optional)</label>
                    <Input
                      placeholder="e.g., https://integrate.api.nvidia.com/v1"
                      value={provider.base_url || ''}
                      onChange={(e) => updateProviderField(index, 'base_url', e.target.value)}
                      className="font-mono text-sm"
                    />
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <div className="flex items-center gap-2">
                      <label className="block text-xs font-medium text-gray-500 mb-1">Enabled</label>
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          checked={provider.enabled}
                          onChange={(e) => toggleProvider(index)}
                          className="sr-only peer"
                        />
                        <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-purple-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-600"></div>
                      </label>
                    </div>
                    {settings.ai_providers.length > 1 && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeProvider(index)}
                        className="text-red-500 hover:text-red-700 hover:bg-red-50 p-1 h-8 w-8"
                        aria-label="Remove provider"
                      >
                        <Trash2 className="w-4 h-4" aria-hidden="true" />
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Google OAuth Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Shield className="w-5 h-5 text-blue-600" aria-hidden="true" />
                Google OAuth Credentials
              </CardTitle>
              <CardDescription>
                Configure Google OAuth client ID and secret for Google account authentication flow.
                These are encrypted at rest and never exposed in API responses.
                <span className="relative inline-block ml-2" title="Values are encrypted and only configured status is shown.">
                  <HelpCircle className="w-4 h-4 inline text-gray-400" aria-hidden="true" />
                </span>
              </CardDescription>
            </div>
            <Button variant="outline" onClick={() => setShowOAuthModal(true)}>
              <Key className="w-4 h-4 mr-2" aria-hidden="true" />
              {settings?.google_oauth_client_id_configured ? 'Update Credentials' : 'Configure'}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Client ID */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Google OAuth Client ID</label>
              <div className="relative">
                <Input
                  type={showClientId ? 'text' : 'password'}
                  value={oauthClientId}
                  onChange={(e) => setOauthClientId(e.target.value)}
                  placeholder={settings?.google_oauth_client_id_configured ? '•••••••• (configured)' : 'Enter Client ID'}
                  className="pr-12"
                  autoComplete="off"
                />
                <button
                  type="button"
                  onClick={() => setShowClientId(!showClientId)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
                  aria-label={showClientId ? 'Hide Client ID' : 'Show Client ID'}
                >
                  {showClientId ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                {settings?.google_oauth_client_id_configured
                  ? 'Client ID is configured (hidden for security)'
                  : 'Not configured'}
              </p>
            </div>

            {/* Client Secret */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Google OAuth Client Secret</label>
              <div className="relative">
                <Input
                  type={showClientSecret ? 'text' : 'password'}
                  value={oauthClientSecret}
                  onChange={(e) => setOauthClientSecret(e.target.value)}
                  placeholder={settings?.google_oauth_client_secret_configured ? '•••••••• (configured)' : 'Enter Client Secret'}
                  className="pr-12"
                  autoComplete="off"
                />
                <button
                  type="button"
                  onClick={() => setShowClientSecret(!showClientSecret)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
                  aria-label={showClientSecret ? 'Hide Client Secret' : 'Show Client Secret'}
                >
                  {showClientSecret ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                {settings?.google_oauth_client_secret_configured
                  ? 'Client Secret is configured (hidden for security)'
                  : 'Not configured'}
              </p>
            </div>
          </div>

          <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="flex items-start gap-3">
              <Key className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" aria-hidden="true" />
              <div className="text-sm text-blue-800">
                <p className="font-medium">Environment Variables (AI Provider API Keys)</p>
                <p className="mt-1">
                  AI provider API keys are read from environment variables on the server.
                  Set them in your <code className="bg-blue-100 px-1 rounded">.env</code> or deployment config:
                </p>
                <ul className="mt-2 list-disc list-inside space-y-1">
                  <li><code className="bg-blue-100 px-1 rounded">NVIDIA_API_KEY</code> — for Nvidia NIM (nemotron-3-ultra-550b)</li>
                  <li><code className="bg-blue-100 px-1 rounded">OPENAI_API_KEY</code> — for OpenAI (if configured)</li>
                  <li><code className="bg-blue-100 px-1 rounded">ANTHROPIC_API_KEY</code> — for Anthropic (if configured)</li>
                </ul>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* OAuth Modal */}
      <Modal
        isOpen={showOAuthModal}
        onClose={() => { setShowOAuthModal(false); setOauthClientId(''); setOauthClientSecret(''); }}
        title="Google OAuth Credentials"
        size="md"
      >
        <form onSubmit={(e) => { e.preventDefault(); handleSaveOAuth(); }} className="space-y-4">
          <p className="text-sm text-gray-600">
            Enter your Google OAuth client credentials from the Google Cloud Console.
            These will be encrypted before storage.
          </p>
          <Input
            label="Client ID"
            placeholder="your-client-id.apps.googleusercontent.com"
            type="text"
            value={oauthClientId}
            onChange={(e) => setOauthClientId(e.target.value)}
            required
          />
          <Input
            label="Client Secret"
            placeholder="GOCSPX-xxxxxxxxxxxx"
            type="password"
            value={oauthClientSecret}
            onChange={(e) => setOauthClientSecret(e.target.value)}
            required
          />
          <div className="flex justify-end gap-3 pt-4 border-t">
            <Button type="button" variant="outline" onClick={() => { setShowOAuthModal(false); setOauthClientId(''); setOauthClientSecret(''); }}>
              Cancel
            </Button>
            <Button type="submit" loading={saving}>
              <Loader2 className="w-4 h-4 mr-2" aria-hidden="true" />
              Save Credentials
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}