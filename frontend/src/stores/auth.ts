import { defineStore } from 'pinia'
import client from '../api/client'

interface User {
  id: number
  username: string
  role: string
  display_name: string | null
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: JSON.parse(localStorage.getItem('user') || 'null') as User | null,
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
    isEnterprise: (s) => s.user?.role === 'enterprise',
  },
  actions: {
    async login(username: string, password: string) {
      const { data } = await client.post('/auth/login', { username, password })
      this._persist(data)
      return data
    },
    async register(payload: {
      username: string
      password: string
      role: string
      display_name?: string
    }) {
      const { data } = await client.post('/auth/register', payload)
      this._persist(data)
      return data
    },
    _persist(data: { access_token: string; user: User }) {
      this.token = data.access_token
      this.user = data.user
      localStorage.setItem('token', data.access_token)
      localStorage.setItem('user', JSON.stringify(data.user))
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    },
  },
})
