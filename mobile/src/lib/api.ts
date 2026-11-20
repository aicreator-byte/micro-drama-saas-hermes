import axios, { AxiosInstance } from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Ganti dengan URL backend saat dijalankan dari HP:
// - Emulator Android: http://10.0.2.2:8001/api/v1
// - iOS simulator: http://localhost:8001/api/v1
// - HP fisik: http://<IP-laptop-di-LAN-yang-sama>:8001/api/v1
export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_URL || 'http://10.0.2.2:8001/api/v1';

export interface Project {
  id: string;
  title: string;
  description?: string | null;
  genre?: string | null;
  status: string;
  created_at: string;
}

export interface AutoGenerateJob {
  id: string;
  project_id: string;
  title: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  steps: { step_key: string; status: string; result_summary?: Record<string, unknown> | null }[];
}

class ApiClient {
  private client: AxiosInstance;
  private token: string | null = null;

  constructor() {
    this.client = axios.create({ baseURL: API_BASE_URL, timeout: 30000 });
    this.client.interceptors.request.use((config) => {
      if (this.token) config.headers.Authorization = `Bearer ${this.token}`;
      return config;
    });
  }

  async init(): Promise<void> {
    this.token = await AsyncStorage.getItem('access_token');
  }

  async login(email: string, password: string): Promise<void> {
    // Backend Hermes memakai JSON {email, password} (bukan OAuth2 form).
    const res = await this.client.post('/auth/login', { email, password });
    this.token = res.data.access_token as string;
    await AsyncStorage.setItem('access_token', this.token);
  }

  async logout(): Promise<void> {
    this.token = null;
    await AsyncStorage.removeItem('access_token');
  }

  isLoggedIn(): boolean {
    return this.token !== null;
  }

  async listProjects(): Promise<Project[]> {
    const res = await this.client.get('/projects', { params: { page: 1, page_size: 50 } });
    return (res.data.items ?? res.data.projects ?? []) as Project[];
  }

  async getProject(id: string): Promise<Project> {
    const res = await this.client.get(`/projects/${id}`);
    return res.data as Project;
  }

  async createProject(title: string, genre?: string): Promise<Project> {
    const res = await this.client.post('/projects', { title, genre });
    return res.data as Project;
  }

  async createAutoGenerateJob(
    projectId: string,
    data: { title: string; genre?: string; num_episodes?: number; premise?: string },
  ): Promise<AutoGenerateJob> {
    const res = await this.client.post(`/projects/${projectId}/auto-generate`, data);
    return res.data as AutoGenerateJob;
  }

  async getAutoGenerateJob(projectId: string, jobId: string): Promise<AutoGenerateJob> {
    const res = await this.client.get(`/projects/${projectId}/auto-generate/${jobId}`);
    return res.data as AutoGenerateJob;
  }
}

export const api = new ApiClient();
