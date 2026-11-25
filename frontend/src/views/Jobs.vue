<template>
  <div>
    <div class="toolbar">
      <h3>职位列表</h3>
      <div>
        <el-button v-if="auth.isEnterprise" @click="openCompany">公司信息</el-button>
        <el-button v-if="auth.isEnterprise" type="primary" @click="dialog = true">发布职位</el-button>
      </div>
    </div>
    <el-table :data="jobs" stripe>
      <el-table-column prop="title" label="职位" />
      <el-table-column prop="company_name" label="公司" />
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

    <el-dialog v-model="dialog" title="发布职位" width="640px">
      <el-form label-width="100px">
        <el-form-item label="职位名称"><el-input v-model="form.title" /></el-form-item>
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
        <el-form-item label="必备技能(逗号分隔)"><el-input v-model="mustSkillsText" placeholder="缺一即淘汰，可留空" /></el-form-item>
        <el-form-item label="岗位类型">
          <el-select v-model="form.job_types" multiple placeholder="可多选">
            <el-option v-for="t in JOB_TYPES" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="理想人才特质">
          <div class="trait-grid">
            <div v-for="t in TRAITS" :key="t.id" class="trait-item">
              <span class="trait-name">{{ t.name }}</span>
              <el-select v-model="traitLevels[t.id]" size="small" style="width: 76px">
                <el-option label="不限" value="不限" />
                <el-option v-for="lv in TRAIT_LEVELS" :key="lv" :label="lv" :value="lv" />
              </el-select>
              <el-checkbox v-model="traitFocus[t.id]" :disabled="traitLevels[t.id] === '不限'" size="small">重点</el-checkbox>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="支持远程"><el-switch v-model="form.remote" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="create">发布</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="companyDialog" title="公司信息" width="680px">
      <el-form label-width="100px">
        <el-form-item label="公司名称"><el-input v-model="companyForm.name" /></el-form-item>
        <el-form-item label="公司简称"><el-input v-model="companyForm.abbr" /></el-form-item>
        <el-form-item label="公司规模">
          <el-select v-model="companyForm.size" clearable placeholder="选择规模">
            <el-option v-for="s in COMPANY_SIZES" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item label="行业"><el-input v-model="companyForm.industry" /></el-form-item>
        <el-form-item label="加班节奏">
          <el-select v-model="companyForm.overtime" clearable placeholder="选择加班情况">
            <el-option v-for="o in OVERTIMES" :key="o" :label="o" :value="o" />
          </el-select>
        </el-form-item>
        <el-form-item label="社保公积金">
          <el-select v-model="companyForm.social_insurance" clearable placeholder="选择缴纳情况">
            <el-option v-for="s in SOCIAL_INSURANCES" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item label="公司特质">
          <CompanyTraitsForm v-model="companyForm.company_traits" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="companyDialog = false">取消</el-button>
        <el-button type="primary" @click="saveCompany">保存</el-button>
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
const jobs = ref<any[]>([])
const dialog = ref(false)
const skillsText = ref('')
const mustSkillsText = ref('')

// 枚举与后端 schemas/requirement.py 常量保持一致
const JOB_TYPES = ['社招', '应届校招', '实习生', '兼职']
const TRAIT_LEVELS = ['弱', '中', '强']
const COMPANY_SIZES = ['1-49人', '50-99人', '100-499人', '500-999人', '1000人以上']
const OVERTIMES = ['不加班', '偶尔加班', '经常加班', '大小周', '996']
const SOCIAL_INSURANCES = ['全额缴纳', '按最低基数缴纳', '无公积金', '面议']
// 人才特质 12 项（TALENT_TRAITS）
const TRAITS = [
  { id: 'C1', name: '结构化' }, { id: 'C2', name: '判断力' }, { id: 'C3', name: '学习迁移' },
  { id: 'A1', name: '主动性' }, { id: 'A2', name: '交付' }, { id: 'A3', name: '韧性' },
  { id: 'S1', name: '表达' }, { id: 'S2', name: '澄清' }, { id: 'S3', name: '冲突' },
  { id: 'M1', name: '成就驱动' }, { id: 'M2', name: '稳定性' }, { id: 'M3', name: '价值取向' },
]
const traitLevels = reactive<Record<string, string>>(
  Object.fromEntries(TRAITS.map((t) => [t.id, '不限'])),
)
const traitFocus = reactive<Record<string, boolean>>(
  Object.fromEntries(TRAITS.map((t) => [t.id, false])),
)

const form = reactive({
  title: '',
  location: '',
  salary_min: null as number | null,
  salary_max: null as number | null,
  education: '本科',
  experience_years: 0,
  industry: '',
  remote: false,
  description: '',
  job_types: [] as string[],
})

const companyDialog = ref(false)
const companyForm = reactive({
  name: '',
  abbr: '',
  size: '',
  industry: '',
  overtime: '',
  social_insurance: '',
  company_traits: {} as Record<string, Record<string, unknown>>,
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

async function loadCompany() {
  if (!auth.isEnterprise) return
  try {
    const { data } = await client.get('/company')
    Object.assign(companyForm, data)
  } catch (e: any) {
    ElMessage.error(e.message)
  }
}

function openCompany() {
  companyDialog.value = true
}

async function saveCompany() {
  try {
    await client.put('/company', { ...companyForm })
    ElMessage.success('已保存')
    companyDialog.value = false
    load()
  } catch (e: any) {
    ElMessage.error(e.message)
  }
}

async function create() {
  try {
    await client.post('/jobs', {
      ...form,
      skills: skillsText.value.split(/[,，、]/).map((s) => s.trim()).filter(Boolean),
      must_skills: mustSkillsText.value.split(/[,，、]/).map((s) => s.trim()).filter(Boolean),
      ideal_talents: TRAITS.filter((t) => traitLevels[t.id] !== '不限').map((t) => ({
        dimension: t.id,
        value: traitLevels[t.id],
        importance: traitFocus[t.id] ? 2.0 : 1.0,
      })),
    })
    ElMessage.success('已发布')
    dialog.value = false
    load()
  } catch (e: any) {
    ElMessage.error(e.message)
  }
}

onMounted(() => {
  load()
  loadCompany()
})
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
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
