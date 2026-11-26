// 公司特质 6 轴定义：表单编辑（CompanyTraitsForm）与详情展示（Jobs.vue）共用，
// 与后端 schemas/requirement.py JOB_FACT_AXES 保持一致（P-S-F-C-V-W 各 3 字段）
export type FieldDef = {
  key: string
  label: string
  type: 'int' | 'select' | 'text'
  min?: number
  max?: number
  options?: string[]
}

export const AXES: { id: string; name: string; fields: FieldDef[] }[] = [
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
