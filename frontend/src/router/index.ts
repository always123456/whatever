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
    { path: '/requirement', component: () => import('../views/Requirement.vue') },
  ],
})

router.beforeEach((to) => {
  if (to.path !== '/login' && !localStorage.getItem('token')) return '/login'
  return true
})

export default router
