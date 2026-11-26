import { ElMessage } from 'element-plus'

/**
 * 企业用户点击提交时的「检测完成」弹窗：展示 0.8 秒后继续执行真正的提交。
 * 调用方式：在提交函数里 await showDetectedToast() 后再发起请求。
 */
export async function showDetectedToast(): Promise<void> {
  ElMessage({ type: 'success', message: '已检测完成，可发布', duration: 800 })
  await new Promise((resolve) => setTimeout(resolve, 800))
}
