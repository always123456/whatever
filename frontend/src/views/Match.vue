<template>
  <div>
    <el-card>
      <h3>智能匹配</h3>
      <p class="tip">
        <template v-if="auth.isEnterprise">
          企业方向：用你最新发布的职位匹配所有求职者；可输入职位 ID（留空则用你最新发布的职位）。
        </template>
        <template v-else>
          求职者方向：用你最新一份简历匹配所有职位。
        </template>
      </p>
      <el-form inline>
        <el-form-item v-if="auth.isEnterprise" label="职位 ID（留空用最新）">
          <el-input-number v-model="targetId" :min="1" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="run">开始匹配</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card style="margin-top: 16px">
      <template #header>匹配结果（共 {{ results.length }} 条）</template>
      <div v-if="!results.length" class="empty">点击「开始匹配」查看结果</div>
      <el-table v-else :data="results" stripe>
        <el-table-column prop="score" label="匹配分" width="100">
          <template #default="{ row }">
            <el-tag :type="row.score >= 0.5 ? 'success' : 'info'">
              {{ row.score.toFixed(3) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="对象" width="160">
          <template #default="{ row }">
            <div>{{ row.payload.name }}</div>
            <div class="sub">{{ row.payload.company }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="payload.location" label="地点" width="90" />
        <el-table-column prop="payload.salary" label="薪资" width="110" />
        <el-table-column prop="payload.education" label="学历" width="80" />
        <el-table-column prop="payload.experience_years" label="经验(年)" width="90" />
        <el-table-column label="技能">
          <template #default="{ row }">{{ (row.payload.skills || []).join('、') }}</template>
        </el-table-column>
        <el-table-column label="硬条件" width="210">
          <template #default="{ row }">
            <el-tag v-for="r in row.matched_rules" :key="r" size="small" type="success" style="margin: 2px">
              {{ r }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="评分明细" min-width="240">
          <template #default="{ row }">
            <div v-for="d in row.dimensions || []" :key="d.key" class="dim-row">
              <div class="dim-head">
                <span class="dim-label">{{ d.label }}</span>
                <span class="dim-score">{{ d.score.toFixed(2) }}</span>
              </div>
              <el-progress
                :percentage="Math.round(d.score * 100)"
                :stroke-width="6"
                :show-text="false"
                class="dim-bar"
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="showDetail(row)">查看详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="detailVisible"
      width="720px"
      top="4vh"
    >
      <template #header>
        <div class="detail-header">
          <span class="detail-title">{{ detail ? `匹配详情 · ${detail.payload.name}` : '匹配详情' }}</span>
          <div class="detail-header-right">
            <el-button
              v-if="auth.isEnterprise"
              size="small"
              type="primary"
              plain
              @click="goApplications"
            >
              投递管理
            </el-button>
            <button class="close-x" type="button" aria-label="Close" @click="detailVisible = false">✕</button>
          </div>
        </div>
      </template>
      <template v-if="detail">
        <div class="total-score">
          <div class="total-score-head">
            <span class="total-score-label">总得分</span>
            <span class="total-score-value">{{ detail.score.toFixed(3) }}</span>
          </div>
          <el-progress
            :percentage="Math.round(detail.score * 100)"
            :stroke-width="10"
            :show-text="false"
            class="dim-bar"
          />
        </div>

        <el-descriptions :column="2" size="small" border class="detail-basic">
          <el-descriptions-item label="对象">{{ detail.payload.name }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.payload.company" label="公司">{{ detail.payload.company }}</el-descriptions-item>
          <el-descriptions-item label="地点">{{ detail.payload.location }}</el-descriptions-item>
          <el-descriptions-item label="薪资">{{ detail.payload.salary }}</el-descriptions-item>
          <el-descriptions-item label="学历">{{ detail.payload.education }}</el-descriptions-item>
          <el-descriptions-item label="经验">{{ detail.payload.experience_years }} 年</el-descriptions-item>
          <el-descriptions-item label="技能" :span="2">{{ (detail.payload.skills || []).join('、') }}</el-descriptions-item>
        </el-descriptions>

        <h4>硬条件对比（岗位要求 vs 求职者）</h4>
        <el-table :data="detail.hard_detail || []" size="small" border>
          <el-table-column prop="label" label="条件" width="100" />
          <el-table-column prop="job_value" label="岗位要求" />
          <el-table-column prop="seeker_value" label="求职者情况" />
          <el-table-column label="结果" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="row.passed ? 'success' : 'danger'" size="small">
                {{ row.passed ? '通过' : '未通过' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>

        <h4>评分明细</h4>
        <div class="detail-dims">
          <div v-for="d in detail.dimensions || []" :key="d.key" class="dim-row">
            <div class="dim-head">
              <span class="dim-label">{{ d.label }}</span>
              <span class="dim-score">{{ d.score.toFixed(2) }}</span>
            </div>
            <el-progress
              :percentage="Math.round(d.score * 100)"
              :stroke-width="8"
              :show-text="false"
              class="dim-bar"
            />
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import client from '../api/client'
import { useAuthStore } from '../stores/auth'
import { showDetectedToast } from '../utils/submitToast'

const auth = useAuthStore()
const router = useRouter()
// 匹配方向跟随账号角色，不再由用户选择
const direction = computed<'seeker_to_jobs' | 'enterprise_to_seekers'>(() =>
  auth.isEnterprise ? 'enterprise_to_seekers' : 'seeker_to_jobs',
)
const targetId = ref<number | undefined>(undefined)
const loading = ref(false)
const results = ref<any[]>([])
const detailVisible = ref(false)
const detail = ref<any>(null)

function showDetail(row: any) {
  detail.value = row
  detailVisible.value = true
}

// 弹窗右上角「投递管理」：跳转到投递管理页（默认落在投递列表 tab）
function goApplications() {
  detailVisible.value = false
  router.push('/applications')
}

async function run() {
  loading.value = true
  try {
    if (auth.isEnterprise) await showDetectedToast()
    const { data } = await client.post('/match', {
      direction: direction.value,
      target_id: auth.isEnterprise ? targetId.value ?? null : null,
    })
    results.value = data.results
    ElMessage.success(`匹配完成，${data.results.length} 条结果`)
  } catch (e: any) {
    ElMessage.error(e.message)
    results.value = []
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.detail-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}
.detail-header-right {
  display: flex;
  align-items: center;
  gap: 14px;
}
.close-x {
  border: none;
  background: transparent;
  padding: 0;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
  color: #909399;
}
.close-x:hover {
  color: #606266;
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
.tip {
  color: #909399;
  font-size: 12px;
  margin: 4px 0 12px;
}
.dim-row {
  margin-bottom: 6px;
}
.dim-row:last-child {
  margin-bottom: 0;
}
.dim-head {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  line-height: 18px;
}
.dim-label {
  color: #606266;
}
.dim-score {
  color: #409eff;
  font-weight: 600;
}
.dim-bar :deep(.el-progress-bar__outer) {
  background-color: #f0f2f5;
}
.detail-basic {
  margin-bottom: 16px;
}
.total-score {
  margin-bottom: 16px;
  padding: 12px 14px;
  background: #f5f7fa;
  border-radius: 6px;
}
.total-score-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 6px;
}
.total-score-label {
  font-size: 14px;
  color: #606266;
}
.total-score-value {
  font-size: 22px;
  font-weight: 700;
  color: #409eff;
}
.detail-dims {
  max-height: 360px;
  overflow-y: auto;
}
h4 {
  margin: 16px 0 10px;
}
</style>
