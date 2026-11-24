<template>
  <el-container class="layout">
    <el-header v-if="auth.isLoggedIn" class="header">
      <span class="title">企业与求职者双向匹配平台</span>
      <el-menu mode="horizontal" :default-active="$route.path" router class="nav">
        <el-menu-item index="/match">智能匹配</el-menu-item>
        <el-menu-item index="/jobs">职位</el-menu-item>
        <el-menu-item index="/resumes">简历</el-menu-item>
      </el-menu>
      <div class="right">
        <span class="who">
          {{ auth.user?.display_name || auth.user?.username }}
          （{{ auth.user?.role === 'enterprise' ? '企业' : '求职者' }}）
        </span>
        <el-button size="small" @click="logout">退出</el-button>
      </div>
    </el-header>
    <el-main>
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'

const auth = useAuthStore()
const router = useRouter()

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<style>
body {
  margin: 0;
  background: #f5f7fa;
}
.layout {
  min-height: 100vh;
}
.header {
  display: flex;
  align-items: center;
  gap: 24px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
}
.title {
  font-weight: 600;
  white-space: nowrap;
}
.nav {
  flex: 1;
  border-bottom: none;
}
.right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.who {
  color: #606266;
  font-size: 14px;
}
</style>
