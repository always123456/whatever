<template>
  <div>
    <el-card>
      <h3>需求卡抽取</h3>
      <p class="tip">粘贴 {{ roleLabel }} 原文，抽取成结构化需求卡预览（供校对后合并进卡）。</p>
      <el-form label-width="90px">
        <el-form-item label="对象类型">
          <el-tag>{{ roleLabel }}</el-tag>
        </el-form-item>
        <el-form-item label="原文">
          <el-input v-model="rawText" type="textarea" :rows="6" :placeholder="`粘贴 ${roleLabel} 原文`" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="parse">抽取</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="card" style="margin-top: 16px">
      <template #header>
        <div class="result-header">
          <span>抽取结果</span>
          <el-button type="success" size="small" :loading="applying" @click="apply">写回（合并进卡）</el-button>
        </div>
      </template>

      <el-alert v-if="warnings.length" type="warning" :closable="false" style="margin-bottom: 12px">
        <div v-for="w in warnings" :key="w">{{ w }}</div>
      </el-alert>

      <el-descriptions :column="3" border size="small">
        <el-descriptions-item label="名称">{{ card.label || '—' }}</el-descriptions-item>
        <el-descriptions-item label="地点">{{ card.hard?.location || '—' }}</el-descriptions-item>
        <el-descriptions-item label="薪资">{{ fmtSalary() }}</el-descriptions-item>
        <el-descriptions-item label="学历">{{ card.hard?.education || '—' }}</el-descriptions-item>
        <el-descriptions-item label="经验(年)">{{ card.hard?.experience_years ?? '—' }}</el-descriptions-item>
        <el-descriptions-item label="远程">{{ card.hard?.remote ? '是' : '否' }}</el-descriptions-item>
        <el-descriptions-item v-if="role === 'enterprise'" label="必备技能">{{ fmtList(card.hard?.must_skills) }}</el-descriptions-item>
        <el-descriptions-item v-if="role === 'enterprise'" label="岗位类型">{{ fmtList(card.hard?.job_types) }}</el-descriptions-item>
        <el-descriptions-item v-if="role === 'seeker'" label="求职状态">{{ card.hard?.job_status || '—' }}</el-descriptions-item>
        <el-descriptions-item label="技能">{{ fmtList(card.soft?.skills) }}</el-descriptions-item>
        <el-descriptions-item label="行业">{{ fmtList(card.soft?.industries) }}</el-descriptions-item>
        <el-descriptions-item v-if="role === 'seeker'" label="意向职位">{{ fmtList(card.soft?.intended_titles) }}</el-descriptions-item>
        <el-descriptions-item v-if="role === 'seeker'" label="意向类型">{{ fmtList(card.soft?.target_job_types) }}</el-descriptions-item>
        <el-descriptions-item label="人才特质">{{ fmtTraits() }}</el-descriptions-item>
      </el-descriptions>

      <h4 style="margin: 16px 0 8px">补充信息（facts）</h4>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item v-for="(v, k) in card.facts" :key="k" :label="factLabel(k)">
          {{ fmtVal(v) }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import client from '../api/client'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
// 对象类型跟随账号角色，不再由用户选择
const role = computed<'seeker' | 'enterprise'>(() => (auth.isEnterprise ? 'enterprise' : 'seeker'))
const roleLabel = computed(() => (role.value === 'enterprise' ? '企业（JD）' : '求职者（简历/自述）'))
const rawText = ref('')
const loading = ref(false)
const applying = ref(false)
const card = ref<any>(null)
const warnings = ref<string[]>([])

const TRAIT_NAMES: Record<string, string> = {
  C1: '结构化', C2: '判断力', C3: '学习迁移',
  A1: '主动性', A2: '交付', A3: '韧性',
  S1: '表达', S2: '澄清', S3: '冲突',
  M1: '成就驱动', M2: '稳定性', M3: '价值取向',
}

const FACT_LABELS: Record<string, string> = {
  is_student: '学生与否', certificates: '证书', work_experiences: '工作/实习经历',
  projects: '项目经历', campus_roles: '在校经历', self_assessment: '自评',
  ideal_company_traits: '理想公司特质', company_name: '公司名', company_abbr: '公司简称',
  company_size: '公司规模', industry: '行业归属', overtime: '加班节奏',
  social_insurance: '社保公积金', company_traits: '公司特质',
}

function factLabel(k: string) {
  return FACT_LABELS[k] || k
}

function fmtList(v?: any[]) {
  return v && v.length ? v.join('、') : '—'
}

function fmtSalary() {
  const lo = card.value?.hard?.salary_min
  const hi = card.value?.hard?.salary_max
  if (lo == null && hi == null) return '面议'
  if (lo == null) return `≤${hi}k`
  if (hi == null) return `≥${lo}k`
  return `${lo}-${hi}k`
}

function fmtTraits() {
  const traits = card.value?.soft?.traits || []
  if (!traits.length) return '—'
  return traits
    .map((t: any) => {
      const name = TRAIT_NAMES[t.dimension] || t.dimension
      const w = t.importance && t.importance !== 1 ? `·重点×${t.importance}` : ''
      return `${name}(${t.value})${w}`
    })
    .join('、')
}

function fmtVal(v: any) {
  if (v === null || v === undefined || v === '') return '—'
  if (Array.isArray(v)) return v.length ? v.join('、') : '—'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

async function parse() {
  if (!rawText.value.trim()) {
    ElMessage.warning('请先粘贴原文')
    return
  }
  loading.value = true
  try {
    const { data } = await client.post('/requirement/parse', {
      role: role.value,
      raw_text: rawText.value,
    })
    card.value = data.card
    warnings.value = data.warnings || []
  } catch (e: any) {
    ElMessage.error(e.message)
    card.value = null
    warnings.value = []
  } finally {
    loading.value = false
  }
}

async function apply() {
  if (!card.value) return
  applying.value = true
  try {
    await client.post('/requirement/apply', {
      role: role.value,
      target_id: null, // 缺省写回当前用户最新一份简历/职位
      card: card.value,
    })
    ElMessage.success('已写回需求卡')
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    applying.value = false
  }
}
</script>

<style scoped>
.tip {
  color: #909399;
  font-size: 12px;
  margin: 0 0 12px;
}
.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
