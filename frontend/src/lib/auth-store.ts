import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User, AuthTokens } from '@/types';
import { api } from '@/lib/api';

interface AuthState {
  user: User | null;
  tokens: AuthTokens | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  setAuth: (user: User, tokens: AuthTokens) => void;
  setUser: (user: User | null) => void;
  logout: () => void;
  checkAuth: () => Promise<boolean>;
  updateUser: (data: Partial<User>) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      tokens: null,
      isLoading: false,
      isAuthenticated: false,

      setAuth: (user: User, tokens: AuthTokens) => {
        api.setToken(tokens.access_token);
        set({ user, tokens, isAuthenticated: true });
      },

      setUser: (user: User | null) => {
        set({ user, isAuthenticated: !!user });
      },

      logout: () => {
        api.logout();
        set({ user: null, tokens: null, isAuthenticated: false });
      },

      checkAuth: async () => {
        const tokens = get().tokens;
        if (!tokens?.access_token) {
          set({ isAuthenticated: false, user: null });
          return false;
        }

        set({ isLoading: true });
        try {
          const user = await api.getCurrentUser();
          set({ user, isAuthenticated: true, isLoading: false });
          return true;
        } catch {
          get().logout();
          set({ isLoading: false });
          return false;
        }
      },

      updateUser: (data: Partial<User>) => {
        const user = get().user;
        if (user) {
          set({ user: { ...user, ...data } });
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ user: state.user, tokens: state.tokens, isAuthenticated: state.isAuthenticated }),
    }
  )
);