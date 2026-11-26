<template>
  <div>
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
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button size="small" @click="open(row)">处理</el-button>
        </template>
      </el-table-column>
    </el-table>

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
            <el-form label-width="90px">
              <el-form-item label="备注">
                <el-input v-model="note" type="textarea" :rows="2" placeholder="可选：如面试时间安排、退回原因" />
              </el-form-item>
              <el-form-item>
                <el-button
                  v-for="act in nextActions"
                  :key="act.status"
                  :type="act.type"
                  :plain="act.type !== 'primary'"
                  @click="act(act.status)"
                >
                  {{ act.label }}
                </el-button>
              </el-form-item>
            </el-form>
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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import client from '../api/client'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const rows = ref<any[]>([])
const loading = ref(false)
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<any>(null)
const note = ref('')

// 与后端 schemas/application.py APPLICATION_STATUSES 一致
const STATUS_TAG: Record<string, string> = {
  待处理: 'info',
  已查看: 'warning',
  面试: 'primary',
  录用: 'success',
  拒绝: 'danger',
}

// 审批按钮与后端状态机 ALLOWED_TRANSITIONS 一致：
// 待处理->已查看/面试/拒绝；已查看->面试/拒绝；面试->录用/拒绝；录用/拒绝终态
const ACTION_DEFS: Record<string, { status: string; label: string; type: string }[]> = {
  待处理: [
    { status: '已查看', label: '标记已查看', type: 'default' },
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
  note.value = ''
  try {
    const { data } = await client.get(`/applications/${row.id}`)
    detail.value = data
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    detailLoading.value = false
  }
}

async function act(status: string) {
  if (!detail.value) return
  try {
    const { data } = await client.patch(`/applications/${detail.value.id}/status`, {
      status,
      note: note.value.trim() || null,
    })
    detail.value = data
    note.value = ''
    ElMessage.success(`已更新为「${status}」`)
    load()
  } catch (e: any) {
    ElMessage.error(e.message)
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
</style>
