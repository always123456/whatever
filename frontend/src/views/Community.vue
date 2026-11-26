<template>
  <div>
    <div class="toolbar">
      <h3>社区评价</h3>
      <p class="sub">真实求职者对岗位的评分与评价，帮你识破注水虚标的职位信息</p>
    </div>

    <div class="picker">
      <span class="label">选择岗位</span>
      <el-select
        v-model="selectedJobId"
        filterable
        placeholder="搜索职位名称 / 公司"
        style="width: 420px"
        @change="onSelectJob"
      >
        <el-option
          v-for="j in jobs"
          :key="j.id"
          :label="`${j.company_name || '未填写公司'} · ${j.title}`"
          :value="j.id"
        />
      </el-select>
    </div>

    <el-card v-if="data" class="panel">
      <div class="head">
        <div class="job-line">
          <span class="job-title">{{ data.job_title }}</span>
          <el-tag v-if="data.company_name" size="small">{{ data.company_name }}</el-tag>
        </div>
        <div class="stats">
          <el-rate :model-value="data.stats.avg_rating ?? 0" disabled allow-half show-score />
          <span class="count">{{ data.stats.count }} 条评价</span>
        </div>
      </div>

      <el-divider />

      <template v-if="auth.isEnterprise">
        <p class="sub">企业账号可查看自己岗位收到的评价，不可发表评价。</p>
      </template>
      <template v-else>
        <div class="write-box">
          <div class="write-title">
            {{ myReview ? '修改我的评价' : '写评价' }}
            <el-tag v-if="myReview" size="small" type="info">你已评价过该岗位</el-tag>
          </div>
          <el-form label-width="90px">
            <el-form-item label="总体评分">
              <el-rate v-model="form.rating" />
            </el-form-item>
            <el-form-item label="文字评价">
              <el-input
                v-model="form.content"
                type="textarea"
                :rows="3"
                maxlength="2000"
                show-word-limit
                placeholder="如实描述：岗位信息是否属实、薪资有无出入、实际工作体验等"
              />
            </el-form-item>
            <el-form-item label="匿名发表">
              <el-switch v-model="form.anonymous" />
              <span class="sub" style="margin-left: 8px">开启后以「匿名求职者」身份展示</span>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :disabled="form.rating === 0" @click="submit">
                {{ myReview ? '保存修改' : '发表评价' }}
              </el-button>
              <el-button v-if="myReview" @click="remove">删除评价</el-button>
            </el-form-item>
          </el-form>
        </div>
        <el-divider />
      </template>

      <div v-if="data.reviews.length" class="reviews">
        <div v-for="r in data.reviews" :key="r.id" class="review">
          <div class="review-head">
            <span class="name">{{ r.reviewer_name }}</span>
            <el-rate :model-value="r.rating" disabled />
            <span class="sub">{{ fmtTime(r.created_at) }}</span>
          </div>
          <div class="review-content">{{ r.content || '（未填写文字评价）' }}</div>
        </div>
      </div>
      <div v-else class="empty">
        <el-empty description="该岗位还没有评价，快来留下第一条真实反馈" :image-size="90" />
      </div>
    </el-card>
    <div v-else class="empty">请先在上方选择一个岗位</div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import client from '../api/client'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

const jobs = ref<any[]>([])
const selectedJobId = ref<number | null>(null)
const data = ref<any>(null)
const myReview = ref<any>(null)

const form = reactive({ rating: 0, content: '', anonymous: false })

async function loadJobs() {
  const { data: list } = await client.get('/jobs')
  jobs.value = list
}

async function loadReviews() {
  if (!selectedJobId.value) {
    data.value = null
    myReview.value = null
    return
  }
  const { data: d } = await client.get('/reviews', { params: { job_id: selectedJobId.value } })
  data.value = d
  myReview.value = d.reviews.find((r: any) => r.is_mine) || null
  if (myReview.value) {
    form.rating = myReview.value.rating
    form.content = myReview.value.content
    form.anonymous = myReview.value.anonymous
  } else {
    form.rating = 0
    form.content = ''
    form.anonymous = false
  }
}

function onSelectJob() {
  loadReviews()
}

async function submit() {
  try {
    if (myReview.value) {
      await client.patch(`/reviews/${myReview.value.id}`, {
        rating: form.rating,
        content: form.content,
        anonymous: form.anonymous,
      })
      ElMessage.success('已保存修改')
    } else {
      await client.post('/reviews', {
        job_id: selectedJobId.value,
        rating: form.rating,
        content: form.content,
        anonymous: form.anonymous,
      })
      ElMessage.success('已发表评价')
    }
    loadReviews()
  } catch (e: any) {
    ElMessage.error(e.message)
  }
}

async function remove() {
  if (!myReview.value) return
  try {
    await client.delete(`/reviews/${myReview.value.id}`)
    ElMessage.success('已删除评价')
    loadReviews()
  } catch (e: any) {
    ElMessage.error(e.message)
  }
}

function fmtTime(s: string) {
  if (!s) return '—'
  return new Date(s).toLocaleString('zh-CN')
}

onMounted(loadJobs)
</script>

<style scoped>
.toolbar {
  margin-bottom: 16px;
}
.toolbar h3 {
  margin: 0 0 4px;
}
.sub {
  color: #909399;
  font-size: 12px;
}
.picker {
  margin-bottom: 16px;
}
.picker .label {
  margin-right: 8px;
  color: #606266;
}
.panel {
  max-width: 860px;
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.job-line {
  display: flex;
  align-items: center;
  gap: 8px;
}
.job-title {
  font-size: 16px;
  font-weight: 600;
}
.stats {
  display: flex;
  align-items: center;
  gap: 8px;
}
.stats .count {
  color: #606266;
  font-size: 13px;
}
.write-box {
  background: #fafafa;
  border-radius: 6px;
  padding: 12px 16px 4px;
}
.write-title {
  font-weight: 600;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.reviews {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.review {
  border-bottom: 1px solid #ebeef5;
  padding-bottom: 12px;
}
.review-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.review-head .name {
  font-weight: 600;
  color: #303133;
}
.review-content {
  color: #606266;
  white-space: pre-wrap;
}
.empty {
  color: #909399;
  padding: 24px;
  text-align: center;
}
</style>
