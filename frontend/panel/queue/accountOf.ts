import type { MaaFWOptionInfo, MaaFWTaskInfo, MaaFWTaskOptionValue } from '../types'

const firstText = (value: unknown): string => {
  if (typeof value === 'string') return value.trim()
  if (value && typeof value === 'object') {
    for (const item of Object.values(value as Record<string, unknown>)) {
      const text = firstText(item)
      if (text) return text
    }
  }
  return ''
}

/**
 * 切号实例的目标账号：任务第一个 input 型选项的第一个输入字段；找不到约定字段时取选项里第一个
 * 非空字符串。与后端 flavor 的 _entry_and_account_readers 同一口径。
 */
export const accountOf = (
  task: MaaFWTaskInfo,
  taskOptions: Record<string, MaaFWTaskOptionValue> | undefined,
  options: readonly MaaFWOptionInfo[]
): string => {
  if (!taskOptions) return ''
  const optionByName = new Map(options.map(option => [option.name, option] as const))
  for (const optionName of task.option || []) {
    const option = optionByName.get(optionName)
    if (option?.type !== 'input' || option.inputs.length === 0) continue
    const value = taskOptions[optionName]
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      return String(value[option.inputs[0].name] ?? '').trim()
    }
    return firstText(value)
  }
  return firstText(taskOptions)
}
