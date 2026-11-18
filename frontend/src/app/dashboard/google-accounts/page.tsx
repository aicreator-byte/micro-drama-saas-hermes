'use client';

import { useEffect, useState } from 'react';
import { useProjectStore } from '@/lib/project-store';
import { api } from '@/lib/api';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { formatDate, cn } from '@/lib/utils';
import { Plus, Edit, Save, Trash2, RefreshCw, Loader2, AlertCircle, CheckCircle, Mail, User, Shield, Key } from 'lucide-react';

const STATUS_LABELS: Record<string, string> = {
  connected: 'Connected',
  disconnected: 'Disconnected',
  expired: 'Expired',
  error: 'Error',
};

const STATUS_COLORS: Record<string, string> = {
  connected: 'bg-green-100 text-green-800',
  disconnected: 'bg-gray-100 text-gray-800',
  expired: 'bg-yellow-100 text-yellow-800',
  error: 'bg-red-100 text-red-800',
};

const STATUS_ICONS: Record<string, React.ReactNode> = {
  connected: <CheckCircle className="w-4 h-4" aria-hidden="true" />,
  disconnected: <Mail className="w-4 h-4" aria-hidden="true" />,
  expired: <AlertCircle className="w-4 h-4" aria-hidden="true" />,
  error: <AlertCircle className="w-4 h-4" aria-hidden="true" />,
};

export default function GoogleAccountsPage() {
  const { googleAccounts, fetchGoogleAccounts, createGoogleAccount, updateGoogleAccount, deleteGoogleAccount, syncGoogleAccount } = useProjectStore();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingAccount, setEditingAccount] = useState<typeof googleAccounts[0] | null>(null);
  const [formData, setFormData] = useState({
    email: '',
    display_name: '',
  });
  const [saving, setSaving] = useState(false);
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    fetchGoogleAccounts();
  }, [fetchGoogleAccounts]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await createGoogleAccount({
        email: formData.email,
        display_name: formData.display_name || undefined,
      });
      setShowCreateModal(false);
      resetForm();
    } catch (error: any) {
      console.error('Failed to create Google account:', error);
      alert(error.response?.data?.detail || 'Failed to create Google account');
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingAccount) return;
    setSaving(true);
    try {
      await updateGoogleAccount(editingAccount.id, {
        display_name: formData.display_name || undefined,
      });
      setEditingAccount(null);
      resetForm();
    } catch (error) {
      console.error('Failed to update Google account:', error);
      alert('Failed to update Google account');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (accountId: string) => {
    if (!confirm('Are you sure you want to disconnect this Google account? This cannot be undone.')) return;
    setDeletingId(accountId);
    try {
      await deleteGoogleAccount(accountId);
    } catch (error: any) {
      console.error('Failed to delete Google account:', error);
      alert(error.response?.data?.detail || 'Failed to delete Google account');
    } finally {
      setDeletingId(null);
    }
  };

  const handleConnectOAuth = async (accountId: string) => {
    setSyncingId(accountId);
    try {
      const { auth_url } = await api.getGoogleAuthUrl(accountId);
      // The callback page needs to know which account the code belongs to.
      sessionStorage.setItem('google_oauth_account_id', accountId);
      window.location.href = auth_url;
    } catch (error: any) {
      console.error('Failed to start Google OAuth:', error);
      alert(error.response?.data?.detail || 'Failed to start Google OAuth. Check that OAuth credentials are configured in Settings.');
    } finally {
      setSyncingId(null);
    }
  };

  const handleSync = async (accountId: string) => {
    setSyncingId(accountId);
    try {
      await syncGoogleAccount(accountId);
      alert('Account synced successfully!');
    } catch (error) {
      console.error('Failed to sync Google account:', error);
      alert('Failed to sync Google account');
    } finally {
      setSyncingId(null);
    }
  };

  const startEdit = (account: typeof googleAccounts[0]) => {
    setEditingAccount(account);
    setFormData({
      email: account.email,
      display_name: account.display_name || '',
    });
  };

  const resetForm = () => {
    setFormData({
      email: '',
      display_name: '',
    });
  };

  const connectedCount = googleAccounts.filter(a => a.status === 'connected').length;
  const maxAccounts = 20;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Google Account Manager</h1>
          <p className="text-gray-600">
            Connect and manage Google accounts for Flow integration. Maximum {maxAccounts} accounts per user.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className={cn('px-3 py-1 rounded-full text-sm font-medium', connectedCount >= maxAccounts ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800')}>
            {connectedCount} / {maxAccounts} connected
          </div>
          <Button onClick={() => { resetForm(); setShowCreateModal(true); }} disabled={connectedCount >= maxAccounts}>
            <Plus className="w-4 h-4 mr-2" aria-hidden="true" />
            Connect Account
          </Button>
        </div>
      </div>

      {/* Info card */}
      <Card className="bg-blue-50 border-blue-200">
        <CardContent className="pt-4">
          <div className="grid gap-4 md:grid-cols-3 text-sm">
            <div className="flex items-start gap-2">
              <Shield className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" aria-hidden="true" />
              <div>
                <p className="font-medium text-blue-900">Encrypted Storage</p>
                <p className="text-blue-700">Session data is encrypted at rest. Never store Google passwords directly.</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <User className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" aria-hidden="true" />
              <div>
                <p className="font-medium text-blue-900">Strict Isolation</p>
                <p className="text-blue-700">Each SaaS user manages their own accounts. No cross-user access.</p>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <Key className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" aria-hidden="true" />
              <div>
                <p className="font-medium text-blue-900">Per-Project Selection</p>
                <p className="text-blue-700">Choose which Google account to use for each project's Flow tasks.</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {googleAccounts.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center">
            <Mail className="w-16 h-16 text-gray-300 mx-auto mb-4" aria-hidden="true" />
            <h3 className="text-lg font-medium text-gray-900 mb-1">No Google accounts connected</h3>
            <p className="text-gray-500 mb-4">Connect your Google account to use with Google Flow integration</p>
            <Button onClick={() => setShowCreateModal(true)} disabled={connectedCount >= maxAccounts}>
              <Plus className="w-4 h-4 mr-2" aria-hidden="true" />
              Connect Account
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {googleAccounts.map((account) => (
            <Card
              key={account.id}
              className={cn('group', editingAccount?.id === account.id && 'ring-2 ring-blue-500')}
            >
              <CardContent className="p-4">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center text-blue-600 flex-shrink-0">
                    <Mail className="w-6 h-6" aria-hidden="true" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-gray-900">{account.email}</h3>
                      {account.display_name && (
                        <span className="text-sm text-gray-500">({account.display_name})</span>
                      )}
                    </div>
                    <div className="mt-1 flex items-center gap-3 text-sm text-gray-500">
                      <span className={cn('px-2 py-0.5 rounded-full', STATUS_COLORS[account.status])} style={{ fontSize: '0.65rem' }}>
                        {STATUS_ICONS[account.status]}
                        {STATUS_LABELS[account.status] || account.status}
                      </span>
                      {account.last_sync && (
                        <span>Last sync: {formatDate(account.last_sync)}</span>
                      )}
                      {account.error_message && (
                        <span className="text-red-600 flex items-center gap-1">
                          <AlertCircle className="w-3 h-3" aria-hidden="true" />
                          {account.error_message}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => handleConnectOAuth(account.id)}
                      disabled={syncingId === account.id}
                      className="px-3 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50"
                      aria-label="Connect via Google OAuth"
                    >
                      Connect via Google
                    </button>
                    <button
                      onClick={() => handleSync(account.id)}
                      disabled={syncingId === account.id}
                      className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors disabled:opacity-50"
                      aria-label="Sync account"
                    >
                      {syncingId === account.id ? (
                        <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
                      ) : (
                        <RefreshCw className="w-4 h-4" aria-hidden="true" />
                      )}
                    </button>
                    <button
                      onClick={() => startEdit(account)}
                      className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                      aria-label="Edit display name"
                    >
                      <Edit className="w-4 h-4" aria-hidden="true" />
                    </button>
                    <button
                      onClick={() => handleDelete(account.id)}
                      disabled={deletingId === account.id}
                      className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50"
                      aria-label="Disconnect account"
                    >
                      {deletingId === account.id ? (
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
        isOpen={showCreateModal || !!editingAccount}
        onClose={() => { setShowCreateModal(false); setEditingAccount(null); resetForm(); }}
        title={editingAccount ? 'Edit Google Account' : 'Connect Google Account'}
        size="md"
      >
        <form onSubmit={editingAccount ? handleUpdate : handleCreate} className="space-y-4">
          {!editingAccount && (
            <>
              <p className="text-sm text-gray-600">
                Enter the Google account email you want to connect. This will be used for Google Flow integration.
                Session data is stored encrypted. You can connect up to {maxAccounts} accounts.
              </p>
              <Input
                label="Google Account Email"
                placeholder="your.email@gmail.com"
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                required
              />
            </>
          )}
          {editingAccount && (
            <>
              <p className="text-sm text-gray-600">
                Editing: <span className="font-medium">{editingAccount.email}</span>
              </p>
              <Input
                label="Display Name"
                placeholder="Optional display name"
                value={formData.display_name}
                onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
              />
            </>
          )}
          <div className="flex justify-end gap-3 pt-4 border-t">
            <Button type="button" variant="outline" onClick={() => { setShowCreateModal(false); setEditingAccount(null); resetForm(); }}>
              Cancel
            </Button>
            <Button type="submit" loading={saving} disabled={editingAccount ? false : connectedCount >= maxAccounts}>
              <Loader2 className="w-4 h-4 mr-2" aria-hidden="true" />
              {editingAccount ? 'Save Changes' : 'Connect Account'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}