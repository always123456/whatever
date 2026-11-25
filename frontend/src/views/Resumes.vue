<template>
  <div>
    <div class="toolbar">
      <h3>{{ auth.isEnterprise ? '投递简历' : '简历列表' }}</h3>
      <el-button v-if="!auth.isEnterprise" type="primary" @click="dialog = true">创建简历</el-button>
    </div>
    <p v-if="auth.isEnterprise" class="tip">仅展示投递了本公司岗位的求职者简历。</p>
    <el-table :data="resumes" stripe>
      <el-table-column prop="name" label="姓名" />
      <el-table-column v-if="auth.isEnterprise" label="投递岗位">
        <template #default="{ row }">{{ (row.applied_job_titles || []).join('、') }}</template>
      </el-table-column>
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

    <el-dialog v-model="dialog" title="创建简历" width="640px">
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
        <el-form-item label="意向职位(逗号分隔,最多5个)"><el-input v-model="intendedTitlesText" /></el-form-item>
        <el-form-item label="求职意向岗位类型">
          <el-select v-model="form.target_job_types" multiple placeholder="可多选">
            <el-option v-for="t in JOB_TYPES" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="人才特质自评">
          <div class="trait-grid">
            <div v-for="t in TRAITS" :key="t.id" class="trait-item">
              <span class="trait-name">{{ t.name }}</span>
              <el-select v-model="selfTraitLevels[t.id]" size="small" style="width: 76px">
                <el-option label="未填" value="" />
                <el-option v-for="lv in TRAIT_LEVELS" :key="lv" :label="lv" :value="lv" />
              </el-select>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="理想公司特质">
          <CompanyTraitsForm v-model="form.ideal_company_traits" />
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
import CompanyTraitsForm from '../components/CompanyTraitsForm.vue'

const auth = useAuthStore()
const resumes = ref<any[]>([])
const dialog = ref(false)
const skillsText = ref('')
const intendedTitlesText = ref('')

// 枚举与后端 schemas/requirement.py 常量保持一致
const JOB_STATUSES = ['随时到岗', '本月到岗', '观望了解']
const JOB_TYPES = ['社招', '应届校招', '实习生', '兼职']
const TRAIT_LEVELS = ['弱', '中', '强']
// 人才特质 12 项（TALENT_TRAITS，与 Jobs.vue 一致）
const TRAITS = [
  { id: 'C1', name: '结构化' }, { id: 'C2', name: '判断力' }, { id: 'C3', name: '学习迁移' },
  { id: 'A1', name: '主动性' }, { id: 'A2', name: '交付' }, { id: 'A3', name: '韧性' },
  { id: 'S1', name: '表达' }, { id: 'S2', name: '澄清' }, { id: 'S3', name: '冲突' },
  { id: 'M1', name: '成就驱动' }, { id: 'M2', name: '稳定性' }, { id: 'M3', name: '价值取向' },
]
const selfTraitLevels = reactive<Record<string, string>>(
  Object.fromEntries(TRAITS.map((t) => [t.id, ''])),
)

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
  target_job_types: [] as string[],
  ideal_company_traits: {} as Record<string, Record<string, unknown>>,
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
      intended_titles: intendedTitlesText.value.split(/[,，、]/).map((s) => s.trim()).filter(Boolean).slice(0, 5),
      self_traits: TRAITS.filter((t) => selfTraitLevels[t.id] !== '').map((t) => ({
        dimension: t.id,
        value: selfTraitLevels[t.id],
      })),
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
.tip {
  color: #909399;
  font-size: 12px;
  margin: 0 0 8px;
}
.trait-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px 16px;
  width: 100%;
}
.trait-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
