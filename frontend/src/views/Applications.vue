<template>
  <div>
    <el-tabs v-model="activeTab" lazy>
      <el-tab-pane label="投递列表" name="apps">
        <div class="toolbar">
          <h3>投递管理</h3>
          <p class="tip">处理本公司岗位收到的投递：查看简历、邀约面试、录用或退回。</p>
        </div>
        <el-table :data="rows" stripe v-loading="loading">
          <el-table-column prop="seeker_name" label="求职者" width="110" />
          <el-table-column prop="job_title" label="投递职位" />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag size="small" :type="STATUS_TAG[row.status] || 'info'">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="投递时间" width="170">
            <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="更新时间" width="170">
            <template #default="{ row }">{{ fmtTime(row.updated_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="170">
            <template #default="{ row }">
              <el-button size="small" @click="jumpToResume(row.resume_id)">简历</el-button>
              <el-button size="small" @click="open(row)">处理</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="投递简历" name="resumes">
        <p class="tip">投递了本公司岗位的求职者简历，按最近投递时间倒序。</p>
        <el-table
          ref="resumeTableRef"
          :data="resumes"
          stripe
          v-loading="resumeLoading"
          row-key="id"
          highlight-current-row
        >
          <el-table-column prop="name" label="姓名" />
          <el-table-column label="投递岗位">
            <template #default="{ row }">{{ (row.applied_job_titles || []).join('、') }}</template>
          </el-table-column>
          <el-table-column label="回复期限" width="110">
            <template #default="{ row }">
              <el-tag v-if="row.reply_deadline_days" type="warning" size="small">
                {{ row.reply_deadline_days }}天内需回复
              </el-tag>
              <span v-else class="sub">—</span>
            </template>
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
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button size="small" @click="openResumeDetail(row)">详细信息</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="detailVisible" :title="detail ? `投递处理 · ${detail.seeker_name} → ${detail.job_title}` : '投递处理'" width="720px" top="4vh">
      <div v-loading="detailLoading" style="max-height: 68vh; overflow-y: auto; padding-right: 4px">
        <template v-if="detail">
          <h4 class="section-title">求职者简历摘要</h4>
          <el-descriptions v-if="detail.resume" :column="2" border>
            <el-descriptions-item label="姓名">{{ detail.resume.name }}</el-descriptions-item>
            <el-descriptions-item label="地点">{{ detail.resume.location }}</el-descriptions-item>
            <el-descriptions-item label="学历">{{ detail.resume.education }}</el-descriptions-item>
            <el-descriptions-item label="经验(年)">{{ detail.resume.experience_years }}</el-descriptions-item>
            <el-descriptions-item label="技能" :span="2">{{ (detail.resume.skills || []).join('、') || '—' }}</el-descriptions-item>
            <el-descriptions-item label="简介" :span="2">{{ detail.resume.summary || '—' }}</el-descriptions-item>
          </el-descriptions>

          <h4 class="section-title">
            状态时间线
            <el-tag size="small" :type="STATUS_TAG[detail.status] || 'info'" style="margin-left: 8px">{{ detail.status }}</el-tag>
            <el-tag
              v-if="['面试', '录用'].includes(detail.status) && (detail.seeker_confirmed_statuses || []).includes(detail.status)"
              size="small"
              type="success"
              style="margin-left: 8px"
            >
              {{ detail.status === '面试' ? '求职者已确认参加面试' : '求职者已确认入职' }}
            </el-tag>
          </h4>
          <el-timeline v-if="(detail.events || []).length">
            <el-timeline-item
              v-for="ev in detail.events"
              :key="ev.id"
              :timestamp="fmtTime(ev.created_at)"
              :type="ev.to_status === '拒绝' ? 'danger' : ev.to_status === '录用' ? 'success' : 'primary'"
            >
              <el-tag size="small" :type="STATUS_TAG[ev.to_status] || 'info'">{{ ev.to_status }}</el-tag>
              <span v-if="ev.note" class="sub note">{{ ev.note }}</span>
              <div class="sub">操作人：{{ ev.operator_name || '—' }}</div>
            </el-timeline-item>
          </el-timeline>
          <p v-else class="sub">暂无流转记录</p>

          <template v-if="nextActions.length">
            <h4 class="section-title">审批操作</h4>
            <div class="action-buttons">
              <el-button
                v-for="actDef in nextActions"
                :key="actDef.status"
                :type="actDef.type"
                :plain="actDef.type !== 'primary'"
                @click="onAction(actDef)"
              >
                {{ actDef.label }}
              </el-button>
            </div>
          </template>
          <el-alert
            v-else
            :title="detail.status === '拒绝' ? '已退回，处理结束' : '已录用，处理结束'"
            type="info"
            :closable="false"
          />
        </template>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resumeDetailVisible" :title="resumeDetail ? `简历详情 · ${resumeDetail.name}` : '简历详情'" width="760px" top="4vh">
      <div v-loading="resumeDetailLoading" style="max-height: 68vh; overflow-y: auto; padding-right: 4px">
        <template v-if="resumeDetail">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="姓名">{{ resumeDetail.name }}</el-descriptions-item>
            <el-descriptions-item label="地点">{{ resumeDetail.location }}</el-descriptions-item>
            <el-descriptions-item label="期望薪资">{{ salary(resumeDetail) }}</el-descriptions-item>
            <el-descriptions-item label="学历">{{ resumeDetail.education }}</el-descriptions-item>
            <el-descriptions-item label="经验(年)">{{ resumeDetail.experience_years }}</el-descriptions-item>
            <el-descriptions-item label="行业">{{ resumeDetail.industry || '—' }}</el-descriptions-item>
            <el-descriptions-item label="求职状态">{{ resumeDetail.job_status || '—' }}</el-descriptions-item>
            <el-descriptions-item label="可远程">{{ resumeDetail.willing_remote ? '是' : '否' }}</el-descriptions-item>
            <el-descriptions-item v-if="resumeDetail.facts?.is_student != null" label="学生身份">
              {{ resumeDetail.facts.is_student ? '是（在读学生）' : '否' }}
            </el-descriptions-item>
            <el-descriptions-item label="更新时间">{{ fmtTime(resumeDetail.updated_at) }}</el-descriptions-item>
            <el-descriptions-item label="意向职位" :span="2">{{ (resumeDetail.intended_titles || []).join('、') || '—' }}</el-descriptions-item>
            <el-descriptions-item label="意向岗位类型" :span="2">{{ (resumeDetail.target_job_types || []).join('、') || '—' }}</el-descriptions-item>
            <el-descriptions-item label="投递岗位" :span="2">{{ (resumeDetail.applied_job_titles || []).join('、') || '—' }}</el-descriptions-item>
            <el-descriptions-item label="技能" :span="2">{{ (resumeDetail.skills || []).join('、') || '—' }}</el-descriptions-item>
            <el-descriptions-item label="简介" :span="2">{{ resumeDetail.summary || '—' }}</el-descriptions-item>
          </el-descriptions>

          <template v-if="traitText">
            <h4 class="section-title">人才特质自评</h4>
            <p class="plain-text">{{ traitText }}</p>
          </template>

          <template v-if="companyTraitText">
            <h4 class="section-title">理想公司特质</h4>
            <p class="plain-text">{{ companyTraitText }}</p>
          </template>

          <template v-if="resumeDetail.raw_text">
            <h4 class="section-title">简历原文（上传解析时留档）</h4>
            <pre class="raw-text">{{ resumeDetail.raw_text }}</pre>
          </template>
        </template>
      </div>
      <template #footer>
        <el-button @click="resumeDetailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="interviewVisible" title="邀约面试 · 选择可面试时间" width="880px" top="4vh">
      <p class="tip">选择企业可面试的空闲时间段（每天 8:00-17:00，每半小时一格），提交后求职者将看到这些时间。</p>
      <div class="slot-week">
        <div v-for="(day, di) in weekDays" :key="di" class="slot-day">
          <div class="slot-day-head">
            <div>{{ day.label }}</div>
            <div class="sub">{{ day.date }}</div>
          </div>
          <div
            v-for="(slot, si) in day.slots"
            :key="si"
            class="slot-box"
            :class="{ selected: selected.has(di + '-' + si) }"
            :title="`${day.label} ${day.date} ${slot.start}-${slot.end}`"
            @click="toggleSlot(di, si)"
          />
        </div>
      </div>
      <div class="slot-summary">
        已选 {{ selected.size }} 个时间段
        <el-button v-if="selected.size" link type="primary" @click="clearSlots">清空</el-button>
      </div>
      <template #footer>
        <el-button @click="interviewVisible = false">取消</el-button>
        <el-button type="primary" :loading="interviewSubmitting" :disabled="!selected.size" @click="submitInterview">
          提交
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="rejectVisible" title="退回 · 请选择退回原因" width="520px" top="10vh">
      <p class="tip">退回必须说明原因（可勾选多项，并补充文字说明），求职者将看到这些反馈。</p>
      <el-checkbox-group v-model="rejectReasons" class="reject-reasons">
        <el-checkbox v-for="r in REJECT_REASONS" :key="r" :value="r">{{ r }}</el-checkbox>
      </el-checkbox-group>
      <el-input
        v-model="rejectNote"
        type="textarea"
        :rows="3"
        placeholder="补充文字说明（可选）"
        style="margin-top: 12px"
      />
      <template #footer>
        <el-button @click="rejectVisible = false">取消</el-button>
        <el-button type="danger" :disabled="!canReject" @click="confirmReject">确认退回</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import client from '../api/client'
import { useAuthStore } from '../stores/auth'
import { AXES } from '../components/companyTraitsAxes'
import { showDetectedToast } from '../utils/submitToast'

const auth = useAuthStore()
const rows = ref<any[]>([])
const loading = ref(false)
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<any>(null)

// —— 退回原因（docx：强制点选原因，复选框 + 文字说明）——
const rejectVisible = ref(false)
const rejectReasons = ref<string[]>([])
const rejectNote = ref('')
const canReject = computed(() => rejectReasons.value.length > 0 || rejectNote.value.trim() !== '')

// 投递简历 tab（原「简历」页企业视图，合并进投递管理）
const activeTab = ref('apps')
const resumes = ref<any[]>([])
const resumeLoading = ref(false)
const resumesLoaded = ref(false)
const resumeTableRef = ref<any>(null)
let resumesPromise: Promise<void> | null = null

// 简历详情弹窗
const resumeDetailVisible = ref(false)
const resumeDetailLoading = ref(false)
const resumeDetail = ref<any>(null)

// 人才特质 9 项，与后端 schemas/requirement.py TALENT_TRAITS 一致
const TALENT_NAMES: Record<string, string> = {
  C1: '结构化', C2: '判断力', C3: '学习迁移',
  A1: '主动性', A2: '交付', A3: '韧性',
  S1: '表达', S2: '澄清', S3: '冲突',
}

function salary(row: any) {
  if (row.expected_salary_min == null && row.expected_salary_max == null) return '面议'
  if (row.expected_salary_min == null) return `≤${row.expected_salary_max}k`
  if (row.expected_salary_max == null) return `≥${row.expected_salary_min}k`
  return `${row.expected_salary_min}-${row.expected_salary_max}k`
}

// 与后端 schemas/application.py APPLICATION_STATUSES 一致
const STATUS_TAG: Record<string, string> = {
  待处理: 'info',
  已查看: 'warning',
  面试: 'primary',
  录用: 'success',
  拒绝: 'danger',
}

// 审批按钮与后端状态机 ALLOWED_TRANSITIONS 一致（已去除「标记已查看」）：
// 待处理->面试/拒绝；已查看(存量)->面试/拒绝；面试->录用/拒绝；录用/拒绝终态
// 「邀约面试」不走 act()，而是打开可面试时间选择弹窗
// 退回原因复选框选项（HR 常见退回原因，可勾选多项 + 文字说明）
const REJECT_REASONS = [
  '学历不符合要求',
  '工作经验不匹配',
  '技能与岗位不符',
  '薪资期望超出预算',
  '岗位已招满',
  '简历信息不完整',
]
const ACTION_DEFS: Record<string, { status: string; label: string; type: string }[]> = {
  待处理: [
    { status: '面试', label: '邀约面试', type: 'primary' },
    { status: '拒绝', label: '退回', type: 'danger' },
  ],
  已查看: [
    { status: '面试', label: '邀约面试', type: 'primary' },
    { status: '拒绝', label: '退回', type: 'danger' },
  ],
  面试: [
    { status: '录用', label: '录用', type: 'success' },
    { status: '拒绝', label: '退回', type: 'danger' },
  ],
}

const nextActions = computed(() => (detail.value ? ACTION_DEFS[detail.value.status] || [] : []))

function fmtTime(s: string) {
  if (!s) return '—'
  return new Date(s).toLocaleString('zh-CN')
}

async function load() {
  loading.value = true
  try {
    const { data } = await client.get('/applications/manage')
    rows.value = data
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function open(row: any) {
  detailVisible.value = true
  detailLoading.value = true
  try {
    const { data } = await client.get(`/applications/${row.id}`)
    detail.value = data
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    detailLoading.value = false
  }
}

function onAction(actDef: { status: string }) {
  // 「邀约面试」打开可面试时间选择弹窗；「退回」打开退回原因弹窗；其余（录用）直接流转
  if (actDef.status === '面试') {
    openInterview()
    return
  }
  if (actDef.status === '拒绝') {
    openReject()
    return
  }
  doTransition(actDef.status)
}

async function doTransition(status: string, noteText: string | null = null) {
  if (!detail.value) return
  try {
    await showDetectedToast()
    const { data } = await client.patch(`/applications/${detail.value.id}/status`, {
      status,
      note: noteText,
    })
    detail.value = data
    ElMessage.success(`已更新为「${status}」`)
    load()
  } catch (e: any) {
    ElMessage.error(e.message)
  }
}

function openReject() {
  rejectReasons.value = []
  rejectNote.value = ''
  rejectVisible.value = true
}

async function confirmReject() {
  if (!detail.value) return
  const parts: string[] = [...rejectReasons.value]
  if (rejectNote.value.trim()) parts.push(`说明：${rejectNote.value.trim()}`)
  rejectVisible.value = false
  await doTransition('拒绝', parts.join('；'))
}

// —— 邀约面试：选择可面试时间（未来一周周一至周日，每天 8:00-17:00 每半小时一格）——
const WEEK_NAMES = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
interface DaySlotDef {
  start: string
  end: string
}
interface DayDef {
  label: string
  date: string
  slots: DaySlotDef[]
}

const weekDays: DayDef[] = (() => {
  const days: DayDef[] = []
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const dow = today.getDay() // 0=周日
  const start = new Date(today)
  if (dow !== 1) start.setDate(today.getDate() + ((8 - dow) % 7)) // 今天不是周一则取下一个周一
  const slots: DaySlotDef[] = []
  for (let h = 8; h < 17; h++) {
    for (const m of [0, 30]) {
      const sh = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
      const eh = m === 0 ? `${String(h).padStart(2, '0')}:30` : `${String(h + 1).padStart(2, '0')}:00`
      slots.push({ start: sh, end: eh })
    }
  }
  for (let i = 0; i < 7; i++) {
    const d = new Date(start)
    d.setDate(start.getDate() + i)
    days.push({
      label: WEEK_NAMES[d.getDay()],
      date: `${d.getMonth() + 1}-${String(d.getDate()).padStart(2, '0')}`,
      slots,
    })
  }
  return days
})()

const interviewVisible = ref(false)
const interviewSubmitting = ref(false)
const selected = ref(new Set<string>())

function openInterview() {
  selected.value = new Set()
  interviewVisible.value = true
}

function toggleSlot(di: number, si: number) {
  const key = `${di}-${si}`
  const s = selected.value
  if (s.has(key)) s.delete(key)
  else s.add(key)
}

function clearSlots() {
  selected.value = new Set()
}

async function submitInterview() {
  if (!detail.value || !selected.value.size) return
  const parts: string[] = []
  weekDays.forEach((day, di) => {
    const daySlots: string[] = []
    day.slots.forEach((s, si) => {
      if (selected.value.has(`${di}-${si}`)) daySlots.push(`${s.start}-${s.end}`)
    })
    if (daySlots.length) parts.push(`${day.date}(${day.label}) ${daySlots.join('、')}`)
  })
  if (!parts.length) return
  interviewSubmitting.value = true
  try {
    await showDetectedToast()
    await client.patch(`/applications/${detail.value.id}/status`, {
      status: '面试',
      note: `可面试时间：${parts.join('；')}`,
    })
    ElMessage.success('已邀约面试')
    interviewVisible.value = false
    detailVisible.value = false
    load()
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    interviewSubmitting.value = false
  }
}

async function loadResumes() {
  // 并发去重：tab 切换 watcher 与「简历」按钮跳转可能同时触发
  if (resumesPromise) return resumesPromise
  resumeLoading.value = true
  resumesPromise = (async () => {
    try {
      const { data } = await client.get('/resumes')
      resumes.value = data
      resumesLoaded.value = true
    } catch (e: any) {
      ElMessage.error(e.message)
    } finally {
      resumeLoading.value = false
    }
  })().finally(() => {
    resumesPromise = null
  })
  return resumesPromise
}

watch(activeTab, (t) => {
  if (t === 'resumes' && !resumesLoaded.value) loadResumes()
})

// 投递列表「简历」按钮：跳到投递简历 tab，高亮并滚动到该投递者所在行
async function jumpToResume(resumeId: number) {
  activeTab.value = 'resumes'
  await loadResumes()
  await nextTick()
  const row = resumes.value.find((r) => r.id === resumeId)
  if (row && resumeTableRef.value) {
    resumeTableRef.value.setCurrentRow(row)
    await nextTick()
    document
      .querySelector('.el-table__row.current-row')
      ?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }
}

// 简历详情弹窗：GET /resumes/{id}（含需求卡 facts + 抽取原文）
const traitText = computed(() => {
  const traits = resumeDetail.value?.self_traits || []
  if (!traits.length) return ''
  return traits
    .map((t: any) => `${TALENT_NAMES[t.dimension] || t.dimension}: ${t.value}`)
    .join('、')
})

const companyTraitText = computed(() => {
  const entries: string[] = []
  const traits = resumeDetail.value?.ideal_company_traits || {}
  for (const axis of AXES) {
    const obj = traits[axis.id]
    if (!obj) continue
    for (const f of axis.fields) {
      const v = obj[f.key]
      if (v !== undefined && v !== null && v !== '') entries.push(`${axis.name}·${f.label}: ${v}`)
    }
  }
  return entries.join('、')
})

async function openResumeDetail(row: any) {
  resumeDetailVisible.value = true
  resumeDetailLoading.value = true
  resumeDetail.value = null
  try {
    const { data } = await client.get(`/resumes/${row.id}`)
    resumeDetail.value = data
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    resumeDetailLoading.value = false
  }
}

onMounted(() => {
  if (!auth.isEnterprise) return
  load()
})
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
  margin: 0;
}
.sub {
  color: #909399;
  font-size: 12px;
}
.note {
  margin-left: 6px;
}
.section-title {
  margin: 16px 0 8px;
}
.plain-text {
  margin: 0;
  color: #606266;
  line-height: 1.6;
}
.raw-text {
  margin: 0;
  max-height: 240px;
  overflow-y: auto;
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 12px;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}
.slot-week {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 6px;
}
.slot-day-head {
  text-align: center;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 4px;
}
.slot-box {
  height: 15px;
  margin-bottom: 3px;
  background: #f0f2f5;
  border: 1px solid #e4e7ed;
  border-radius: 2px;
  cursor: pointer;
  transition: background 0.1s;
}
.slot-box:hover {
  border-color: #409eff;
}
.slot-box.selected {
  background: #409eff;
  border-color: #409eff;
}
.slot-summary {
  margin-top: 10px;
  font-size: 13px;
  color: #606266;
}
.action-buttons {
  display: flex;
  gap: 12px;
}
.reject-reasons {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
</style>
