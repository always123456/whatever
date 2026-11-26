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
    company: null as any, // 企业账号的公司档案（登录/刷新后加载，供各处预填）
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
    async fetchCompany() {
      // 企业账号登录后加载公司档案；失败不阻塞登录流程
      if (!this.isEnterprise) return null
      try {
        const { data } = await client.get('/company')
        this.company = data
        return data
      } catch {
        return null
      }
    },
    logout() {
      this.token = ''
      this.user = null
      this.company = null
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    },
  },
})
