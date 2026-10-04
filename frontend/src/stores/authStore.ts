import { create } from 'zustand'

interface User {
  id: string
  username: string
  display_name: string
  email: string | null
  department: string
  role: string
  security_level: string
  channel_scope: string
}

interface AuthState {
  token: string | null
  refreshToken: string | null
  user: User | null
  isAuthenticated: boolean
  login: (token: string, refreshToken: string, user: User) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => {
  // 从 localStorage 恢复
  const savedToken = localStorage.getItem('askkb_token')
  const savedRefresh = localStorage.getItem('askkb_refresh')
  const savedUser = localStorage.getItem('askkb_user')

  return {
    token: savedToken,
    refreshToken: savedRefresh,
    user: savedUser ? JSON.parse(savedUser) : null,
    isAuthenticated: !!savedToken,

    login: (token, refreshToken, user) => {
      localStorage.setItem('askkb_token', token)
      localStorage.setItem('askkb_refresh', refreshToken)
      localStorage.setItem('askkb_user', JSON.stringify(user))
      set({ token, refreshToken, user, isAuthenticated: true })
    },

    logout: () => {
      localStorage.removeItem('askkb_token')
      localStorage.removeItem('askkb_refresh')
      localStorage.removeItem('askkb_user')
      set({ token: null, refreshToken: null, user: null, isAuthenticated: false })
    },
  }
})