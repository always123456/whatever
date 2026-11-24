<template>
  <div>
    <el-card>
      <h3>智能匹配</h3>
      <el-form inline>
        <el-form-item label="匹配方向">
          <el-radio-group v-model="direction">
            <el-radio value="seeker_to_jobs">求职者 → 职位</el-radio>
            <el-radio value="enterprise_to_seekers">企业 → 求职者</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="run">开始匹配</el-button>
        </el-form-item>
      </el-form>
      <p class="tip">
        求职者方向用你最新一份简历匹配所有职位；企业方向可输入职位 ID（留空则用你最新发布的职位）。
      </p>
      <el-form-item v-if="direction === 'enterprise_to_seekers'" label="职位 ID（留空用最新）">
        <el-input-number v-model="targetId" :min="1" />
      </el-form-item>
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
        <el-table-column label="评分明细">
          <template #default="{ row }">
            <div v-for="r in row.reasons" :key="r" class="sub">{{ r }}</div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import client from '../api/client'

const direction = ref<'seeker_to_jobs' | 'enterprise_to_seekers'>('seeker_to_jobs')
const targetId = ref<number | undefined>(undefined)
const loading = ref(false)
const results = ref<any[]>([])

async function run() {
  loading.value = true
  try {
    const { data } = await client.post('/match', {
      direction: direction.value,
      target_id: direction.value === 'enterprise_to_seekers' ? targetId.value ?? null : null,
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
</style>
