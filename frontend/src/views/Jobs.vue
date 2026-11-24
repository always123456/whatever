<template>
  <div>
    <div class="toolbar">
      <h3>职位列表</h3>
      <el-button v-if="auth.isEnterprise" type="primary" @click="dialog = true">发布职位</el-button>
    </div>
    <el-table :data="jobs" stripe>
      <el-table-column prop="title" label="职位" />
      <el-table-column prop="company" label="公司" />
      <el-table-column prop="location" label="地点" />
      <el-table-column label="薪资">
        <template #default="{ row }">{{ salary(row) }}</template>
      </el-table-column>
      <el-table-column prop="education" label="学历" />
      <el-table-column prop="experience_years" label="经验(年)" />
      <el-table-column label="技能">
        <template #default="{ row }">{{ (row.skills || []).join('、') }}</template>
      </el-table-column>
      <el-table-column label="远程">
        <template #default="{ row }">{{ row.remote ? '支持' : '—' }}</template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog" title="发布职位" width="520px">
      <el-form label-width="100px">
        <el-form-item label="职位名称"><el-input v-model="form.title" /></el-form-item>
        <el-form-item label="公司"><el-input v-model="form.company" /></el-form-item>
        <el-form-item label="地点"><el-input v-model="form.location" /></el-form-item>
        <el-form-item label="薪资下限(k)"><el-input-number v-model="form.salary_min" :min="0" /></el-form-item>
        <el-form-item label="薪资上限(k)"><el-input-number v-model="form.salary_max" :min="0" /></el-form-item>
        <el-form-item label="最低学历">
          <el-select v-model="form.education">
            <el-option v-for="e in ['不限', '大专', '本科', '硕士', '博士']" :key="e" :label="e" :value="e" />
          </el-select>
        </el-form-item>
        <el-form-item label="经验年数"><el-input-number v-model="form.experience_years" :min="0" /></el-form-item>
        <el-form-item label="行业"><el-input v-model="form.industry" /></el-form-item>
        <el-form-item label="技能(逗号分隔)"><el-input v-model="skillsText" /></el-form-item>
        <el-form-item label="支持远程"><el-switch v-model="form.remote" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="create">发布</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import client from '../api/client'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const jobs = ref<any[]>([])
const dialog = ref(false)
const skillsText = ref('')
const form = reactive({
  title: '',
  company: '',
  location: '',
  salary_min: null as number | null,
  salary_max: null as number | null,
  education: '本科',
  experience_years: 0,
  industry: '',
  remote: false,
  description: '',
})

function salary(row: any) {
  if (row.salary_min == null && row.salary_max == null) return '面议'
  if (row.salary_min == null) return `≤${row.salary_max}k`
  if (row.salary_max == null) return `≥${row.salary_min}k`
  return `${row.salary_min}-${row.salary_max}k`
}

async function load() {
  const { data } = await client.get('/jobs')
  jobs.value = data
}

async function create() {
  try {
    await client.post('/jobs', {
      ...form,
      skills: skillsText.value.split(/[,，、]/).map((s) => s.trim()).filter(Boolean),
    })
    ElMessage.success('已发布')
    dialog.value = false
    load()
  } catch (e: any) {
    ElMessage.error(e.message)
  }
}

onMounted(load)
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
