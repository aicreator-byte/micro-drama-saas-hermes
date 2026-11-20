import { useState } from 'react';
import { View } from 'react-native';
import { registerRootComponent } from 'expo';
import { StatusBar } from 'expo-status-bar';
import { LoginScreen } from './src/screens/LoginScreen';
import { ProjectsScreen } from './src/screens/ProjectsScreen';
import { ProjectDetailScreen } from './src/screens/ProjectDetailScreen';

export type Screen =
  | { name: 'login' }
  | { name: 'projects' }
  | { name: 'detail'; projectId: string };

export default function App() {
  const [screen, setScreen] = useState<Screen>({ name: 'login' });

  return (
    <View style={{ flex: 1, backgroundColor: '#fff' }}>
      <StatusBar style="auto" />
      {screen.name === 'login' && (
        <LoginScreen onLoggedIn={() => setScreen({ name: 'projects' })} />
      )}
      {screen.name === 'projects' && (
        <ProjectsScreen
          onOpen={(projectId) => setScreen({ name: 'detail', projectId })}
          onLogout={() => setScreen({ name: 'login' })}
        />
      )}
      {screen.name === 'detail' && (
        <ProjectDetailScreen
          projectId={screen.projectId}
          onBack={() => setScreen({ name: 'projects' })}
        />
      )}
    </View>
  );
}

registerRootComponent(App);
