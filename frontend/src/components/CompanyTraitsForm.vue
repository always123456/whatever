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
import { AXES } from './companyTraitsAxes'

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
