<template>
  <div class="axes">
    <div v-for="axis in AXES" :key="axis.id" class="axis-block">
      <div class="axis-name">{{ axis.id }} · {{ axis.name }}</div>
      <div class="axis-field" v-for="f in axis.fields" :key="f.key">
        <span class="field-label">{{ f.label }}</span>
        <el-input-number
          v-if="f.type === 'int'"
          v-model="vals[axis.id][f.key]"
          :min="f.min"
          :max="f.max"
          :controls="false"
          size="small"
          placeholder="未填"
          style="width: 120px"
        />
        <el-select
          v-else-if="f.type === 'select'"
          v-model="vals[axis.id][f.key]"
          size="small"
          clearable
          placeholder="未填"
          style="width: 120px"
        >
          <el-option v-for="o in f.options" :key="o" :label="o" :value="o" />
        </el-select>
        <el-input
          v-else
          v-model="vals[axis.id][f.key]"
          size="small"
          placeholder="未填"
          style="width: 120px"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, reactive, watch } from 'vue'

// 与后端 schemas/requirement.py JOB_FACT_AXES 保持一致（P-S-F-C-V-W 各 3 字段）
type FieldDef = {
  key: string
  label: string
  type: 'int' | 'select' | 'text'
  min?: number
  max?: number
  options?: string[]
}
const AXES: { id: string; name: string; fields: FieldDef[] }[] = [
  {
    id: 'P', name: '节奏', fields: [
      { key: 'busy_months', label: '忙季每年几个月', type: 'int', min: 0, max: 12 },
      { key: 'busy_week_hours', label: '忙季周工时', type: 'int', min: 0, max: 168 },
      { key: 'response_hours', label: '日常消息响应期望', type: 'int', min: 0, max: 168 },
    ],
  },
  {
    id: 'S', name: '结构', fields: [
      { key: 'decision_layers', label: '到决策者几层', type: 'int', min: 1, max: 5 },
      { key: 'decision_days', label: '需求平均决策天数', type: 'int', min: 0, max: 365 },
      { key: 'process_docs', label: '流程文档化', type: 'select', options: ['无', '部分', '完整'] },
    ],
  },
  {
    id: 'F', name: '反馈', fields: [
      { key: 'one_on_one', label: '1v1 频率', type: 'select', options: ['周', '月', '季', '无'] },
      { key: 'feedback_from', label: '谁给反馈', type: 'select', options: ['直属', '上级', '无'] },
      { key: 'promotion_cycle', label: '晋升评审周期', type: 'text' },
    ],
  },
  {
    id: 'C', name: '协作', fields: [
      { key: 'division', label: '分工方式', type: 'select', options: ['按模块', '按人', '混合'] },
      { key: 'channel', label: '主沟通渠道', type: 'select', options: ['口头', '文档', '两者'] },
      { key: 'dispute_owner', label: '分歧谁定', type: 'select', options: ['直属', '上级', '集体'] },
    ],
  },
  {
    id: 'V', name: '价值', fields: [
      { key: 'perf_metric', label: '绩效看结果还是过程', type: 'select', options: ['结果', '过程'] },
      { key: 'reward', label: '奖励团队还是个人', type: 'select', options: ['团队', '个人'] },
      { key: 'stability', label: '偏好稳定还是变化', type: 'select', options: ['稳定', '变化'] },
    ],
  },
  {
    id: 'W', name: '形态', fields: [
      { key: 'office_days', label: '每周到岗天数', type: 'int', min: 0, max: 7 },
      { key: 'travel_days', label: '每月出差天数', type: 'int', min: 0, max: 31 },
      { key: 'cross_tz', label: '跨时区协作', type: 'select', options: ['有', '无'] },
    ],
  },
]

const props = defineProps<{ modelValue: Record<string, Record<string, unknown>> }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: Record<string, Record<string, unknown>>): void }>()

const vals = reactive<Record<string, Record<string, unknown>>>({})

function initVals() {
  for (const axis of AXES) {
    const src = (props.modelValue && props.modelValue[axis.id]) || {}
    vals[axis.id] = {}
    for (const f of axis.fields) {
      vals[axis.id][f.key] = src[f.key] ?? null
    }
  }
}
initVals()

// 外部回填（如编辑公司档案）时重灌；灌入期间不触发 emit，避免回环
let syncing = false
watch(
  () => props.modelValue,
  () => {
    syncing = true
    initVals()
    nextTick(() => (syncing = false))
  },
  { deep: true },
)

// 规范化序列化（键排序），用于判断输出是否与当前 modelValue 一致，打断回环
function canon(v: unknown): string {
  if (v === null || v === undefined) return 'null'
  if (Array.isArray(v)) return `[${v.map(canon).join(',')}]`
  if (typeof v === 'object') {
    const keys = Object.keys(v as object).sort()
    return `{${keys.map((k) => `${JSON.stringify(k)}:${canon((v as Record<string, unknown>)[k])}`).join(',')}}`
  }
  return JSON.stringify(v)
}

// 只提交已填的字段；空轴整段省略；与当前值一致则不 emit（避免回环）
function emitValue() {
  const out: Record<string, Record<string, unknown>> = {}
  for (const axis of AXES) {
    const axisObj: Record<string, unknown> = {}
    for (const f of axis.fields) {
      const v = vals[axis.id][f.key]
      if (v !== null && v !== undefined && v !== '') axisObj[f.key] = v
    }
    if (Object.keys(axisObj).length > 0) out[axis.id] = axisObj
  }
  if (canon(out) === canon(props.modelValue || {})) return
  emit('update:modelValue', out)
}
watch(vals, () => {
  if (!syncing) emitValue()
}, { deep: true })
</script>

<style scoped>
.axes {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 20px;
  width: 100%;
}
.axis-block {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 8px 10px;
}
.axis-name {
  font-weight: 600;
  font-size: 13px;
  color: #303133;
  margin-bottom: 6px;
}
.axis-field {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin: 4px 0;
}
.field-label {
  font-size: 12px;
  color: #606266;
}
</style>
