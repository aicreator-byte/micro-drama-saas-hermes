import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Button,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { api, Project } from '../lib/api';

export function ProjectsScreen({
  onOpen,
  onLogout,
}: {
  onOpen: (projectId: string) => void;
  onLogout: () => void;
}) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [newTitle, setNewTitle] = useState('');

  const load = useCallback(async () => {
    try {
      setError('');
      setProjects(await api.listProjects());
    } catch (e) {
      setError('Gagal memuat proyek — periksa koneksi & URL backend.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const create = async () => {
    if (!newTitle.trim()) return;
    try {
      const p = await api.createProject(newTitle.trim());
      setNewTitle('');
      setProjects((prev) => [p, ...prev]);
    } catch (e) {
      setError('Gagal membuat proyek.');
    }
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Proyek</Text>
        <Button title="Keluar" onPress={async () => { await api.logout(); onLogout(); }} />
      </View>
      {error ? <Text style={styles.error}>{error}</Text> : null}
      <View style={styles.row}>
        <TextInput
          style={[styles.input, { flex: 1 }]}
          placeholder="Judul proyek baru"
          value={newTitle}
          onChangeText={setNewTitle}
        />
        <Button title="+ Buat" onPress={create} />
      </View>
      <FlatList
        data={projects}
        keyExtractor={(p) => p.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        ListEmptyComponent={<Text style={styles.empty}>Belum ada proyek. Buat satu di atas.</Text>}
        renderItem={({ item }) => (
          <TouchableOpacity style={styles.card} onPress={() => onOpen(item.id)}>
            <Text style={styles.cardTitle}>{item.title}</Text>
            <Text style={styles.cardMeta}>
              {item.genre || 'tanpa genre'} • {item.status}
            </Text>
          </TouchableOpacity>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, paddingTop: 48 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  title: { fontSize: 24, fontWeight: 'bold' },
  error: { color: '#c00', marginBottom: 8 },
  row: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  input: { borderWidth: 1, borderColor: '#ccc', borderRadius: 8, padding: 10 },
  empty: { color: '#666', textAlign: 'center', marginTop: 32 },
  card: { borderWidth: 1, borderColor: '#e5e5e5', borderRadius: 10, padding: 14, marginBottom: 10 },
  cardTitle: { fontSize: 16, fontWeight: '600' },
  cardMeta: { color: '#666', marginTop: 4 },
});
