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
      <el-table-column v-if="!auth.isEnterprise" label="操作" width="200">
        <template #default="{ row }">
          <el-button size="small" @click="showDetail(row)">详情</el-button>
          <el-button
            size="small"
            :type="appliedJobIds.has(row.id) ? 'info' : 'primary'"
            :disabled="appliedJobIds.has(row.id)"
            @click="apply(row)"
          >
            {{ appliedJobIds.has(row.id) ? '已投递' : '投递' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="detailVisible" :title="detail ? `职位详情 · ${detail.job.title}` : '职位详情'" width="780px" top="3vh">
      <div v-loading="detailLoading" style="max-height: 72vh; overflow-y: auto; padding-right: 4px">
        <template v-if="detail">
          <el-tabs>
            <el-tab-pane label="岗位详情">
              <el-descriptions :column="2" border>
                <el-descriptions-item label="公司">{{ detail.job.company_name || '—' }}</el-descriptions-item>
                <el-descriptions-item label="职位">{{ detail.job.title }}</el-descriptions-item>
                <el-descriptions-item label="地点">{{ detail.job.location }}</el-descriptions-item>
                <el-descriptions-item label="薪资">{{ salary(detail.job) }}</el-descriptions-item>
                <el-descriptions-item label="学历要求">{{ detail.job.education }}</el-descriptions-item>
                <el-descriptions-item label="经验要求">{{ detail.job.experience_years }} 年</el-descriptions-item>
                <el-descriptions-item label="行业">{{ detail.job.industry || '—' }}</el-descriptions-item>
                <el-descriptions-item label="岗位类型">{{ (detail.job.job_types || []).join('、') || '—' }}</el-descriptions-item>
                <el-descriptions-item label="技能">{{ (detail.job.skills || []).join('、') || '—' }}</el-descriptions-item>
                <el-descriptions-item label="必备技能">{{ (detail.job.must_skills || []).join('、') || '—' }}</el-descriptions-item>
                <el-descriptions-item label="远程">{{ detail.job.remote ? '支持' : '不支持' }}</el-descriptions-item>
                <el-descriptions-item label="状态">{{ detail.job.status === 'active' ? '招聘中' : '已关闭' }}</el-descriptions-item>
                <el-descriptions-item label="职位描述" :span="2">{{ detail.job.description || '—' }}</el-descriptions-item>
              </el-descriptions>
              <h4 class="section-title">公司情况</h4>
              <el-descriptions v-if="detail.company" :column="2" border>
                <el-descriptions-item label="规模">{{ detail.company.size || '—' }}</el-descriptions-item>
                <el-descriptions-item label="行业">{{ detail.company.industry || '—' }}</el-descriptions-item>
                <el-descriptions-item label="加班节奏">{{ detail.company.overtime || '—' }}</el-descriptions-item>
                <el-descriptions-item label="社保公积金">{{ detail.company.social_insurance || '—' }}</el-descriptions-item>
                <el-descriptions-item label="资质审查">
                  <el-tag v-if="detail.company.verified" type="success" size="small">通过资质审查</el-tag>
                  <span v-else class="sub">未认证</span>
                </el-descriptions-item>
              </el-descriptions>
              <p v-else class="sub">该公司暂未填写档案</p>
              <div v-if="companyTraitEntries(detail.company).length" class="traits">
                <el-tag v-for="(v, k) in companyTraitEntries(detail.company)" :key="k" size="small" style="margin: 2px">
                  {{ k }}：{{ v }}
                </el-tag>
              </div>
            </el-tab-pane>
            <el-tab-pane label="匹配度分析">
              <div v-if="!detail.match || !detail.match.resume_id" class="empty">
                你还没有简历，去「简历」页创建一份后，即可查看与该岗位的匹配度。
              </div>
              <template v-else>
                <p class="sub">分析对象：你的简历「{{ detail.match.resume_name }}」</p>
                <div v-if="detail.match.hard_passed">
                  <div class="score">{{ (detail.match.score * 100).toFixed(1) }}<span class="pct">%</span></div>
                  <el-tag v-for="r in detail.match.matched_rules" :key="r" size="small" type="success" style="margin: 2px">{{ r }}</el-tag>
                  <div class="reasons">
                    <div v-for="r in detail.match.reasons" :key="r" class="sub">· {{ r }}</div>
                  </div>
                </div>
                <div v-else>
                  <el-alert title="硬条件未通过，未进入打分" type="warning" :closable="false" style="margin-bottom: 8px" />
                  <el-tag v-for="r in detail.match.matched_rules" :key="r" size="small" type="success" style="margin: 2px">{{ r }}</el-tag>
                  <el-tag v-for="r in detail.match.failed_rules" :key="r" size="small" type="danger" style="margin: 2px">{{ r }}</el-tag>
                </div>
              </template>
            </el-tab-pane>
            <el-tab-pane label="简历进度">
              <template v-if="detail.application">
                <el-alert
                  v-if="detail.application.status === '拒绝'"
                  title="很遗憾，该职位申请未通过"
                  type="error"
                  :closable="false"
                  style="margin-bottom: 12px"
                />
                <el-steps
                  v-else
                  :active="STATUS_STEP[detail.application.status] ?? 0"
                  :finish-status="detail.application.status === '录用' ? 'success' : 'process'"
                  align-center
                  style="margin: 16px 0"
                >
                  <el-step v-for="s in APPLICATION_STEP_STATUSES" :key="s" :title="s" />
                </el-steps>
                <el-descriptions :column="2" border>
                  <el-descriptions-item label="当前状态">{{ detail.application.status }}</el-descriptions-item>
                  <el-descriptions-item label="投递时间">{{ fmtTime(detail.application.created_at) }}</el-descriptions-item>
                  <el-descriptions-item label="更新时间">{{ fmtTime(detail.application.updated_at) }}</el-descriptions-item>
                </el-descriptions>
                <div v-if="CONFIRMABLE_STATUSES.includes(detail.application.status)" class="confirm-box">
                  <template v-if="isConfirmed(detail.application)">
                    <el-tag type="success" size="small">
                      {{ detail.application.status === '面试' ? '已确认参加面试' : '已确认入职' }}
                    </el-tag>
                  </template>
                  <template v-else>
                    <span class="sub">企业已发出{{ detail.application.status === '面试' ? '面试邀约' : '录用通知' }}，请确认：</span>
                    <el-button size="small" type="primary" @click="confirmSeeker">
                      {{ detail.application.status === '面试' ? '确认参加面试' : '确认入职' }}
                    </el-button>
                  </template>
                </div>
                <h4 class="section-title">状态时间线</h4>
                <el-timeline v-if="(detail.application.events || []).length">
                  <el-timeline-item
                    v-for="ev in detail.application.events"
                    :key="ev.id"
                    :timestamp="fmtTime(ev.created_at)"
                    :type="ev.to_status === '拒绝' ? 'danger' : ev.to_status === '录用' ? 'success' : 'primary'"
                  >
                    <el-tag size="small" :type="STATUS_TAG[ev.to_status] || 'info'">{{ ev.to_status }}</el-tag>
                    <span v-if="ev.note" class="sub" style="margin-left: 6px">{{ ev.note }}</span>
                    <div class="sub">操作人：{{ ev.operator_name || '—' }}</div>
                  </el-timeline-item>
                </el-timeline>
                <p v-else class="sub">暂无流转记录</p>
              </template>
              <div v-else class="empty">
                尚未投递该职位
                <el-button type="primary" size="small" style="margin-left: 8px" @click="applyDetail">立即投递</el-button>
              </div>
            </el-tab-pane>
          </el-tabs>
        </template>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button v-if="detail && !detail.application" type="primary" @click="applyDetail">投递</el-button>
      </template>
    </el-dialog>

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
      <div class="company-pdf-row">
        <el-button size="small" @click="openCompanyPdf">上传 PDF 自动提取</el-button>
        <span class="sub">支持公司简介/营业执照等文字层 PDF，解析后自动填充表单；未识别字段保留原值</span>
      </div>
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
        <el-form-item label="资质审查">
          <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap">
            <el-tag v-if="companyForm.verified" type="success" size="large">通过资质审查</el-tag>
            <template v-else>
              <el-upload
                :auto-upload="false"
                :limit="1"
                :show-file-list="false"
                accept=".jpg,.jpeg,.png,.webp,.pdf,.doc,.docx"
                :on-change="onVerifyFileChange"
                :on-remove="onVerifyFileRemove"
              >
                <el-button size="small">选择资质文件</el-button>
              </el-upload>
              <span v-if="verifyFile" class="sub">{{ verifyFile.name }}</span>
              <el-button
                size="small"
                type="primary"
                :disabled="!verifyFile"
                :loading="verifying"
                @click="submitVerify"
              >
                上传并审查
              </el-button>
            </template>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="companyDialog = false">取消</el-button>
        <el-button type="primary" @click="saveCompany">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="companyPdfDialog" title="公司信息 PDF 自动提取" width="720px">
      <template v-if="!companyPdfCard">
        <el-upload
          drag
          :auto-upload="false"
          :limit="1"
          accept=".pdf"
          :on-change="onCompanyPdfChange"
          :on-remove="onCompanyPdfRemove"
          :file-list="[]"
        >
          <div class="el-upload__text">将公司资料 PDF 拖到此处，或<em>点击选择</em>（仅支持文字层 PDF）</div>
        </el-upload>
        <div class="upload-actions">
          <el-button type="primary" :loading="companyPdfParsing" :disabled="!companyPdfFile" @click="parseCompanyPdf">
            解析
          </el-button>
        </div>
      </template>
      <template v-else>
        <el-alert v-if="companyPdfWarnings.length" type="warning" :closable="false" style="margin-bottom: 12px">
          <div v-for="w in companyPdfWarnings" :key="w">{{ w }}</div>
        </el-alert>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="公司名称">{{ companyPdfCard.name || '—' }}</el-descriptions-item>
          <el-descriptions-item label="公司简称">{{ companyPdfCard.abbr || '—' }}</el-descriptions-item>
          <el-descriptions-item label="公司规模">{{ companyPdfCard.size || '—' }}</el-descriptions-item>
          <el-descriptions-item label="行业">{{ companyPdfCard.industry || '—' }}</el-descriptions-item>
          <el-descriptions-item label="加班节奏">{{ companyPdfCard.overtime || '—' }}</el-descriptions-item>
          <el-descriptions-item label="社保公积金">{{ companyPdfCard.social_insurance || '—' }}</el-descriptions-item>
        </el-descriptions>
        <p v-if="companyPdfCard.description" class="sub" style="margin: 10px 0 0">
          识别到的公司简介（仅供预览，不入库）：{{ companyPdfCard.description }}
        </p>
        <p class="sub" style="margin: 10px 0 0">确认写入后，非空字段将覆盖表单对应值，未识别字段保留原值。</p>
        <div class="upload-actions">
          <el-button @click="resetCompanyPdf">重新上传</el-button>
          <el-button type="success" :loading="companyPdfApplying" @click="applyCompanyPdf">确认写入公司信息</el-button>
        </div>
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
import { AXES } from '../components/companyTraitsAxes'
import { showDetectedToast } from '../utils/submitToast'

const auth = useAuthStore()
const jobs = ref<any[]>([])
const dialog = ref(false)
const skillsText = ref('')
const mustSkillsText = ref('')
const appliedJobIds = ref<Set<number>>(new Set())

// 职位详情弹窗
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<any>(null)

// 投递状态枚举与后端 schemas/application.py APPLICATION_STATUSES 一致；
// 步骤条展示 待处理→已查看→面试→录用，拒绝单独提示
const APPLICATION_STEP_STATUSES = ['待处理', '已查看', '面试', '录用']
const STATUS_STEP: Record<string, number> = { 待处理: 0, 已查看: 1, 面试: 2, 录用: 3 }
const STATUS_TAG: Record<string, string> = {
  待处理: 'info',
  已查看: 'warning',
  面试: 'primary',
  录用: 'success',
  拒绝: 'danger',
}

// 求职者可确认的状态档位（与后端 SEEKER_CONFIRMABLE 一致）
const CONFIRMABLE_STATUSES = ['面试', '录用']

// 枚举与后端 schemas/requirement.py 常量保持一致
const JOB_TYPES = ['社招', '应届校招', '实习生', '兼职']
const TRAIT_LEVELS = ['弱', '中', '强']
const COMPANY_SIZES = ['1-49人', '50-99人', '100-499人', '500-999人', '1000人以上']
const OVERTIMES = ['不加班', '偶尔加班', '经常加班', '大小周', '996']
const SOCIAL_INSURANCES = ['全额缴纳', '按最低基数缴纳', '无公积金', '面议']
// 人才特质 9 项（TALENT_TRAITS）
const TRAITS = [
  { id: 'C1', name: '结构化' }, { id: 'C2', name: '判断力' }, { id: 'C3', name: '学习迁移' },
  { id: 'A1', name: '主动性' }, { id: 'A2', name: '交付' }, { id: 'A3', name: '韧性' },
  { id: 'S1', name: '表达' }, { id: 'S2', name: '澄清' }, { id: 'S3', name: '冲突' },
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
  verified: false,
  verified_at: null as string | null,
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

async function loadApplications() {
  if (auth.isEnterprise) return
  try {
    const { data } = await client.get('/applications')
    appliedJobIds.value = new Set(data.map((a: any) => a.job_id))
  } catch (e: any) {
    ElMessage.error(e.message)
  }
}

async function apply(row: any) {
  try {
    await client.post('/applications', { job_id: row.id })
    ElMessage.success(`已投递「${row.title}」`)
    loadApplications()
  } catch (e: any) {
    ElMessage.error(e.message)
  }
}

async function showDetail(row: any) {
  detailVisible.value = true
  detailLoading.value = true
  try {
    const { data } = await client.get(`/jobs/${row.id}/detail`)
    detail.value = data
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    detailLoading.value = false
  }
}

async function applyDetail() {
  if (!detail.value) return
  await apply(detail.value.job)
  await showDetail(detail.value.job) // 刷新：投递状态与进度
}

function isConfirmed(app: any) {
  return (app.seeker_confirmed_statuses || []).includes(app.status)
}

async function confirmSeeker() {
  if (!detail.value?.application) return
  const appId = detail.value.application.id
  const isInterview = detail.value.application.status === '面试'
  try {
    const { data } = await client.post(`/applications/${appId}/confirm`, {})
    detail.value = { ...detail.value, application: data }
    ElMessage.success(isInterview ? '已确认参加面试' : '已确认入职')
  } catch (e: any) {
    ElMessage.error(e.message)
  }
}

function fmtTime(s: string) {
  if (!s) return '—'
  return new Date(s).toLocaleString('zh-CN')
}

function companyTraitEntries(company: any): Record<string, string> {
  const out: Record<string, string> = {}
  const traits = company?.company_traits || {}
  for (const axis of AXES) {
    const obj = traits[axis.id]
    if (!obj) continue
    for (const f of axis.fields) {
      const v = obj[f.key]
      if (v !== undefined && v !== null && v !== '') out[`${axis.name}·${f.label}`] = String(v)
    }
  }
  return out
}

async function loadCompany() {
  if (!auth.isEnterprise) return
  try {
    const { data } = await client.get('/company')
    Object.assign(companyForm, data)
    auth.company = data // 保持登录态里的公司档案与服务器同步
  } catch (e: any) {
    ElMessage.error(e.message)
  }
}

function openCompany() {
  // 登录时已把公司档案拉进 store，先预填再向服务器刷新
  if (auth.company) Object.assign(companyForm, auth.company)
  loadCompany()
  companyDialog.value = true
}

async function saveCompany() {
  try {
    await showDetectedToast()
    await client.put('/company', { ...companyForm })
    ElMessage.success('已保存')
    companyDialog.value = false
    load()
  } catch (e: any) {
    ElMessage.error(e.message)
  }
}

// —— 资质审查（简化版）：上传资质文件即通过 ——
const verifyFile = ref<File | null>(null)
const verifying = ref(false)

function onVerifyFileChange(uploadFile: any) {
  verifyFile.value = uploadFile.raw ?? null
}

function onVerifyFileRemove() {
  verifyFile.value = null
}

async function submitVerify() {
  if (!verifyFile.value) return
  verifying.value = true
  try {
    await showDetectedToast()
    const fd = new FormData()
    fd.append('file', verifyFile.value)
    const { data } = await client.post('/company/verify', fd)
    Object.assign(companyForm, data)
    auth.company = data // 保持登录态里的公司档案与服务器同步
    ElMessage.success('已通过资质审查')
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    verifying.value = false
  }
}

// —— 公司信息 PDF 自动提取（两段式：解析出预览 → 确认合并写入）——
const companyPdfDialog = ref(false)
const companyPdfFile = ref<File | null>(null)
const companyPdfParsing = ref(false)
const companyPdfApplying = ref(false)
const companyPdfCard = ref<any>(null)
const companyPdfWarnings = ref<string[]>([])

function openCompanyPdf() {
  resetCompanyPdf()
  companyPdfDialog.value = true
}

function resetCompanyPdf() {
  companyPdfFile.value = null
  companyPdfCard.value = null
  companyPdfWarnings.value = []
}

function onCompanyPdfChange(uploadFile: any) {
  const raw = uploadFile.raw as File
  if (!raw.name.toLowerCase().endsWith('.pdf')) {
    ElMessage.warning('仅支持 PDF 文件')
    return
  }
  companyPdfFile.value = raw
}

function onCompanyPdfRemove() {
  companyPdfFile.value = null
}

async function parseCompanyPdf() {
  if (!companyPdfFile.value) return
  companyPdfParsing.value = true
  try {
    const fd = new FormData()
    fd.append('file', companyPdfFile.value)
    const { data } = await client.post('/company/parse-pdf', fd)
    companyPdfCard.value = data.company
    companyPdfWarnings.value = data.warnings || []
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    companyPdfParsing.value = false
  }
}

async function applyCompanyPdf() {
  if (!companyPdfCard.value) return
  companyPdfApplying.value = true
  try {
    await showDetectedToast()
    const { data } = await client.post('/company/apply-extracted', {
      company: companyPdfCard.value,
    })
    Object.assign(companyForm, data)
    auth.company = data // 保持登录态里的公司档案与服务器同步
    ElMessage.success('已提取并写入公司信息，请核对后保存')
    companyPdfDialog.value = false
    resetCompanyPdf()
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    companyPdfApplying.value = false
  }
}

async function create() {
  try {
    await showDetectedToast()
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
  loadApplications()
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
.section-title {
  margin: 16px 0 8px;
}
.sub {
  color: #909399;
  font-size: 12px;
}
.empty {
  color: #909399;
  padding: 24px;
  text-align: center;
}
.score {
  font-size: 32px;
  font-weight: 600;
  color: #67c23a;
  margin-bottom: 8px;
}
.pct {
  font-size: 16px;
  margin-left: 2px;
}
.reasons {
  margin-top: 12px;
}
.traits {
  margin-top: 8px;
}
.confirm-box {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 12px 0;
}
.company-pdf-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}
.upload-actions {
  margin-top: 12px;
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}
</style>
