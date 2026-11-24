import axios from 'axios'

const client = axios.create({ baseURL: '/api', timeout: 15000 })

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

client.interceptors.response.use(
  (resp) => resp,
  (err) => {
    const detail = err?.response?.data?.detail
    if (err?.response?.status === 401 && location.pathname !== '/login') {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      location.href = '/login'
    }
    return Promise.reject(
      new Error(typeof detail === 'string' ? detail : err.message || '请求失败'),
    )
  },
)

export default client
