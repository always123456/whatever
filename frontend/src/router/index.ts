import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/match' },
    { path: '/login', component: () => import('../views/Login.vue') },
    { path: '/match', component: () => import('../views/Match.vue') },
    { path: '/jobs', component: () => import('../views/Jobs.vue') },
    { path: '/resumes', component: () => import('../views/Resumes.vue') },
    { path: '/applications', component: () => import('../views/Applications.vue') },
    { path: '/community', component: () => import('../views/Community.vue') },
    { path: '/requirement', component: () => import('../views/Requirement.vue') },
  ],
})

router.beforeEach((to) => {
  if (to.path !== '/login' && !localStorage.getItem('token')) return '/login'
  // 简历页仅求职者使用；企业视图已合并进「投递管理」
  const user = JSON.parse(localStorage.getItem('user') || 'null')
  if (to.path === '/resumes' && user?.role === 'enterprise') return '/applications'
  return true
})

export default router
