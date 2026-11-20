import { useEffect, useState } from 'react';
import { ActivityIndicator, Button, StyleSheet, Text, TextInput, View } from 'react-native';
import { api, AutoGenerateJob, Project } from '../lib/api';

export function ProjectDetailScreen({
  projectId,
  onBack,
}: {
  projectId: string;
  onBack: () => void;
}) {
  const [project, setProject] = useState<Project | null>(null);
  const [job, setJob] = useState<AutoGenerateJob | null>(null);
  const [numEpisodes, setNumEpisodes] = useState('5');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api.getProject(projectId).then(setProject).catch(() => setError('Gagal memuat proyek.'));
  }, [projectId]);

  // Polling status job tiap 2 detik selagi running (backend async, sama seperti web).
  useEffect(() => {
    if (!job || (job.status !== 'running' && job.status !== 'pending')) return;
    const t = setInterval(async () => {
      try {
        const fresh = await api.getAutoGenerateJob(projectId, job.id);
        setJob(fresh);
      } catch (e) {
        // biarkan polling berikutnya mencoba lagi
      }
    }, 2000);
    return () => clearInterval(t);
  }, [job, projectId]);

  const startAutoGenerate = async () => {
    if (!project) return;
    setBusy(true);
    setError('');
    try {
      const created = await api.createAutoGenerateJob(projectId, {
        title: project.title,
        genre: project.genre || undefined,
        num_episodes: Math.max(1, Math.min(50, Number(numEpisodes) || 5)),
      });
      setJob(created);
    } catch (e) {
      setError('Gagal memulai auto-generate.');
    } finally {
      setBusy(false);
    }
  };

  if (!project) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" />
        {error ? <Text style={styles.error}>{error}</Text> : null}
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Button title="‹ Kembali ke proyek" onPress={onBack} />
      <Text style={styles.title}>{project.title}</Text>
      <Text style={styles.meta}>
        {project.genre || 'tanpa genre'} • {project.status}
      </Text>
      {project.description ? <Text style={styles.desc}>{project.description}</Text> : null}

      <Text style={styles.section}>Auto-Generate</Text>
      <Text style={styles.hint}>AI mengisi bible, karakter, lokasi, episode, dan prompt dari judul.</Text>
      <View style={styles.row}>
        <Text>Jumlah episode:</Text>
        <TextInput
          style={styles.numInput}
          keyboardType="number-pad"
          value={numEpisodes}
          onChangeText={setNumEpisodes}
        />
        <Button title={busy ? 'Memulai…' : 'Mulai Auto-Generate'} onPress={startAutoGenerate} disabled={busy} />
      </View>
      {error ? <Text style={styles.error}>{error}</Text> : null}

      {job && (
        <View style={styles.job}>
          <Text style={styles.jobTitle}>Job: {job.status}</Text>
          {job.steps.map((s) => (
            <Text key={s.step_key} style={styles.step}>
              {s.step_key}: {s.status}
            </Text>
          ))}
          {job.status === 'completed' && (
            <Text style={styles.done}>Selesai — buka di web untuk melihat bible, karakter, dan episode.</Text>
          )}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, paddingTop: 48 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  title: { fontSize: 24, fontWeight: 'bold', marginTop: 12 },
  meta: { color: '#666', marginTop: 4 },
  desc: { marginTop: 8, color: '#333' },
  section: { fontSize: 18, fontWeight: 'bold', marginTop: 24 },
  hint: { color: '#666', marginTop: 4, marginBottom: 12 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  numInput: { borderWidth: 1, borderColor: '#ccc', borderRadius: 8, padding: 8, width: 56, textAlign: 'center' },
  error: { color: '#c00', marginTop: 8 },
  job: { marginTop: 16, borderWidth: 1, borderColor: '#e5e5e5', borderRadius: 10, padding: 12 },
  jobTitle: { fontWeight: 'bold', marginBottom: 6 },
  step: { color: '#333', marginTop: 2 },
  done: { color: 'green', marginTop: 8 },
});
