<template>
  <div>
    <div class="toolbar">
      <h3>简历列表</h3>
      <el-button v-if="!auth.isEnterprise" type="primary" @click="dialog = true">创建简历</el-button>
    </div>
    <el-table :data="resumes" stripe>
      <el-table-column prop="name" label="姓名" />
      <el-table-column prop="location" label="地点" />
      <el-table-column label="期望薪资">
        <template #default="{ row }">{{ salary(row) }}</template>
      </el-table-column>
      <el-table-column prop="education" label="学历" />
      <el-table-column prop="experience_years" label="经验(年)" />
      <el-table-column prop="industry" label="行业" />
      <el-table-column label="技能">
        <template #default="{ row }">{{ (row.skills || []).join('、') }}</template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog" title="创建简历" width="520px">
      <el-form label-width="100px">
        <el-form-item label="姓名"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="地点"><el-input v-model="form.location" /></el-form-item>
        <el-form-item label="期望下限(k)"><el-input-number v-model="form.expected_salary_min" :min="0" /></el-form-item>
        <el-form-item label="期望上限(k)"><el-input-number v-model="form.expected_salary_max" :min="0" /></el-form-item>
        <el-form-item label="学历">
          <el-select v-model="form.education">
            <el-option v-for="e in ['不限', '大专', '本科', '硕士', '博士']" :key="e" :label="e" :value="e" />
          </el-select>
        </el-form-item>
        <el-form-item label="经验年数"><el-input-number v-model="form.experience_years" :min="0" /></el-form-item>
        <el-form-item label="行业"><el-input v-model="form.industry" /></el-form-item>
        <el-form-item label="技能(逗号分隔)"><el-input v-model="skillsText" /></el-form-item>
        <el-form-item label="求职状态">
          <el-select v-model="form.job_status">
            <el-option v-for="s in JOB_STATUSES" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item label="可远程"><el-switch v-model="form.willing_remote" /></el-form-item>
        <el-form-item label="简介"><el-input v-model="form.summary" type="textarea" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="create">创建</el-button>
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
const resumes = ref<any[]>([])
const dialog = ref(false)
const skillsText = ref('')

// 枚举与后端 schemas/requirement.py JOB_STATUSES 保持一致
const JOB_STATUSES = ['随时到岗', '本月到岗', '观望了解']

const form = reactive({
  name: '',
  location: '',
  expected_salary_min: null as number | null,
  expected_salary_max: null as number | null,
  education: '本科',
  experience_years: 0,
  industry: '',
  willing_remote: false,
  summary: '',
  job_status: '',
})

function salary(row: any) {
  if (row.expected_salary_min == null && row.expected_salary_max == null) return '面议'
  if (row.expected_salary_min == null) return `≤${row.expected_salary_max}k`
  if (row.expected_salary_max == null) return `≥${row.expected_salary_min}k`
  return `${row.expected_salary_min}-${row.expected_salary_max}k`
}

async function load() {
  const { data } = await client.get('/resumes')
  resumes.value = data
}

async function create() {
  try {
    await client.post('/resumes', {
      ...form,
      skills: skillsText.value.split(/[,，、]/).map((s) => s.trim()).filter(Boolean),
    })
    ElMessage.success('已创建')
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
