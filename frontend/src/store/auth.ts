import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { UserResponse } from '../types/api';

interface AuthState {
  token: string | null;
  user: UserResponse | null;
  isAuthenticated: boolean;
  setToken: (token: string) => void;
  setUser: (user: UserResponse) => void;
  logout: () => void;
  setDemoMode: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      
      setToken: (token: string) => {
        set({ token, isAuthenticated: true });
      },
      
      setUser: (user: UserResponse) => {
        set({ user });
      },
      
      logout: () => {
        set({ token: null, user: null, isAuthenticated: false });
      },
      
      setDemoMode: () => {
        const demoUser: UserResponse = {
          id: 0,
          email: 'guest@demo.local',
          created_at: new Date().toISOString(),
        };
        set({ 
          token: 'demo-token-' + Date.now(), 
          user: demoUser, 
          isAuthenticated: true 
        });
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ token: state.token }),
    }
  )
);
