<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <h2>企业与求职者双向匹配平台</h2>
      <el-tabs v-model="tab">
        <el-tab-pane label="登录" name="login" />
        <el-tab-pane label="注册" name="register" />
      </el-tabs>
      <el-form label-width="80px" @submit.prevent>
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password placeholder="密码" />
        </el-form-item>
        <el-form-item v-if="tab === 'register'" label="角色">
          <el-radio-group v-model="form.role">
            <el-radio value="seeker">求职者</el-radio>
            <el-radio value="enterprise">企业</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="tab === 'register'" label="昵称">
          <el-input v-model="form.display_name" placeholder="可选" />
        </el-form-item>
        <el-button type="primary" style="width: 100%" :loading="loading" @click="submit">
          {{ tab === 'login' ? '登录' : '注册并登录' }}
        </el-button>
      </el-form>
      <p class="hint">
        演示账号（密码均 123456）：企业 enterprise1；求职者 seeker1 ~ seeker4
      </p>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const tab = ref('login')
const loading = ref(false)
const form = reactive({ username: '', password: '', role: 'seeker', display_name: '' })

async function submit() {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    if (tab.value === 'login') {
      await auth.login(form.username, form.password)
    } else {
      await auth.register({
        username: form.username,
        password: form.password,
        role: form.role,
        display_name: form.display_name,
      })
    }
    ElMessage.success('欢迎')
    router.push('/match')
  } catch (e: any) {
    ElMessage.error(e.message || '操作失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  display: flex;
  justify-content: center;
  padding-top: 60px;
}
.login-card {
  width: 400px;
}
.hint {
  color: #909399;
  font-size: 12px;
  margin-top: 12px;
}
</style>
