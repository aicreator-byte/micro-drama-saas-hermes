import { useState } from 'react';
import { Alert, Button, StyleSheet, Text, TextInput, View } from 'react-native';
import { api } from '../lib/api';

export function LoginScreen({ onLoggedIn }: { onLoggedIn: () => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!email.trim() || !password) {
      Alert.alert('Login', 'Isi email dan password.');
      return;
    }
    setBusy(true);
    try {
      await api.init();
      await api.login(email.trim(), password);
      onLoggedIn();
    } catch (e) {
      Alert.alert('Login gagal', 'Periksa email/password dan URL backend (EXPO_PUBLIC_API_URL).');
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Micro Drama SaaS</Text>
      <Text style={styles.subtitle}>Masuk dengan akun yang sama seperti di web.</Text>
      <TextInput
        style={styles.input}
        placeholder="Email"
        autoCapitalize="none"
        keyboardType="email-address"
        value={email}
        onChangeText={setEmail}
      />
      <TextInput
        style={styles.input}
        placeholder="Password"
        secureTextEntry
        value={password}
        onChangeText={setPassword}
      />
      <Button title={busy ? 'Masuk…' : 'Masuk'} onPress={submit} disabled={busy} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', padding: 24 },
  title: { fontSize: 28, fontWeight: 'bold', marginBottom: 8 },
  subtitle: { color: '#666', marginBottom: 24 },
  input: { borderWidth: 1, borderColor: '#ccc', borderRadius: 8, padding: 12, marginBottom: 12 },
});
