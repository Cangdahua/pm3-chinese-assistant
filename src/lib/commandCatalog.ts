export type CommandGroupId =
  | 'all'
  | 'device'
  | 'hf'
  | 'lf'
  | 'mifare'
  | 'data'
  | 'scripts'
  | 'security'
  | 'settings'
  | 'discovered'

export type CommandRisk = 'normal' | 'write' | 'advanced'

export type Pm3Command = {
  id: string
  groupId: CommandGroupId
  label: string
  command: string
  description: string
  tags: string[]
  risk?: CommandRisk
  source?: 'builtin' | 'discovered'
}

export type CommandGroup = {
  id: CommandGroupId
  label: string
  accent: string
  commands: Pm3Command[]
}

const makeCommand = (
  groupId: CommandGroupId,
  command: string,
  label: string,
  description: string,
  tags: string[] = [],
  risk: CommandRisk = 'normal',
): Pm3Command => ({
  id: `${groupId}:${command}`,
  groupId,
  label,
  command,
  description,
  tags,
  risk,
  source: 'builtin',
})

export const commandGroups: CommandGroup[] = [
  {
    id: 'device',
    label: '设备',
    accent: '#0f766e',
    commands: [
      makeCommand('device', 'hw version', '版本', '客户端、固件、硬件信息', ['hw', 'version']),
      makeCommand('device', 'hw status', '状态', '设备运行状态', ['hw', 'status']),
      makeCommand('device', 'hw tune', '天线', 'HF/LF 天线调谐', ['hw', 'tune']),
      makeCommand('device', 'hw ping', '通信', '连接测试', ['hw', 'ping']),
      makeCommand('device', 'hw reset', '重启', '重置设备', ['hw', 'reset'], 'advanced'),
      makeCommand('device', 'hw bootloader', '引导', '进入 Bootloader', ['hw', 'bootloader'], 'advanced'),
      makeCommand('device', 'hw detectreader', '读卡器', '检测外部读卡器', ['hw', 'reader']),
      makeCommand('device', 'mem info', '内存', '设备内存状态', ['mem', 'info']),
    ],
  },
  {
    id: 'hf',
    label: '高频 HF',
    accent: '#2563eb',
    commands: [
      makeCommand('hf', 'hf search', '搜索', '自动识别 HF 标签', ['hf', 'search']),
      makeCommand('hf', 'hf tune', '调谐', 'HF 天线调谐', ['hf', 'tune']),
      makeCommand('hf', 'hf list', '列表', 'HF 捕获数据列表', ['hf', 'list']),
      makeCommand('hf', 'hf 14a reader', 'ISO14443A', '读取 14A 标签', ['hf', '14a']),
      makeCommand('hf', 'hf 14a info', '14A 信息', '14A 标签信息', ['hf', '14a', 'info']),
      makeCommand('hf', 'hf 14b info', '14B 信息', '14B 标签信息', ['hf', '14b', 'info']),
      makeCommand('hf', 'hf felica reader', 'FeliCa', 'FeliCa 读取', ['hf', 'felica']),
      makeCommand('hf', 'hf iclass info', 'iCLASS', 'iCLASS 信息', ['hf', 'iclass']),
      makeCommand('hf', 'hf legic info', 'LEGIC', 'LEGIC 信息', ['hf', 'legic']),
      makeCommand('hf', 'hf topaz reader', 'Topaz', 'Topaz 读取', ['hf', 'topaz']),
      makeCommand('hf', 'hf st25tb info', 'ST25TB', 'ST25TB 信息', ['hf', 'st25tb']),
      makeCommand('hf', 'hf emv search', 'EMV', 'EMV 卡搜索', ['hf', 'emv']),
    ],
  },
  {
    id: 'mifare',
    label: 'MIFARE',
    accent: '#7c3aed',
    commands: [
      makeCommand('mifare', 'hf mf info', '信息', 'MIFARE Classic 信息', ['hf', 'mf']),
      makeCommand('mifare', 'hf mf chk', '密钥检查', 'Classic 密钥检查', ['hf', 'mf', 'key']),
      makeCommand('mifare', 'hf mf autopwn', '自动分析', 'MIFARE Classic 自动分析', ['hf', 'mf', 'autopwn'], 'advanced'),
      makeCommand('mifare', 'hf mf dump', '导出', 'Classic 数据导出', ['hf', 'mf', 'dump']),
      makeCommand('mifare', 'hf mf restore', '写回', 'Classic 数据写回', ['hf', 'mf', 'restore'], 'write'),
      makeCommand('mifare', 'hf mf nested', '嵌套分析', 'MIFARE Classic 嵌套分析流程', ['hf', 'mf', 'nested'], 'advanced'),
      makeCommand('mifare', 'hf mf hardnested', '强化嵌套分析', 'MIFARE Classic 强化嵌套分析流程', ['hf', 'mf', 'hardnested'], 'advanced'),
      makeCommand('mifare', 'hf mf sim', '模拟', 'Classic 模拟', ['hf', 'mf', 'sim'], 'advanced'),
      makeCommand('mifare', 'hf mf sniff', '嗅探', 'Classic 通信嗅探', ['hf', 'mf', 'sniff']),
      makeCommand('mifare', 'hf mfu info', 'Ultralight', 'Ultralight 信息', ['hf', 'mfu']),
      makeCommand('mifare', 'hf mfu dump', 'UL 导出', 'Ultralight 数据导出', ['hf', 'mfu', 'dump']),
      makeCommand('mifare', 'hf mfu restore', 'UL 写回', 'Ultralight 数据写回', ['hf', 'mfu', 'restore'], 'write'),
    ],
  },
  {
    id: 'lf',
    label: '低频 LF',
    accent: '#b45309',
    commands: [
      makeCommand('lf', 'lf search', '搜索', '自动识别 LF 标签', ['lf', 'search']),
      makeCommand('lf', 'lf tune', '调谐', 'LF 天线调谐', ['lf', 'tune']),
      makeCommand('lf', 'lf read', '采样', '读取 LF 波形', ['lf', 'read']),
      makeCommand('lf', 'lf config', '配置', 'LF 采样配置', ['lf', 'config']),
      makeCommand('lf', 'lf hid read', 'HID', 'HID Prox 读取', ['lf', 'hid']),
      makeCommand('lf', 'lf hid clone', 'HID 写卡', 'HID Prox 克隆', ['lf', 'hid', 'clone'], 'write'),
      makeCommand('lf', 'lf hid sim', 'HID 模拟', 'HID Prox 模拟', ['lf', 'hid', 'sim'], 'advanced'),
      makeCommand('lf', 'lf em 410x_read', 'EM410x', 'EM410x 读取', ['lf', 'em']),
      makeCommand('lf', 'lf em 410x_clone', 'EM 写卡', 'EM410x 克隆', ['lf', 'em', 'clone'], 'write'),
      makeCommand('lf', 'lf t55xx detect', 'T55xx', 'T55xx 检测', ['lf', 't55xx']),
      makeCommand('lf', 'lf t55xx dump', 'T55xx 导出', 'T55xx 数据导出', ['lf', 't55xx', 'dump']),
      makeCommand('lf', 'lf t55xx write', 'T55xx 写入', 'T55xx 块写入', ['lf', 't55xx', 'write'], 'write'),
      makeCommand('lf', 'lf indala read', 'Indala', 'Indala 读取', ['lf', 'indala']),
      makeCommand('lf', 'lf awid read', 'AWID', 'AWID 读取', ['lf', 'awid']),
    ],
  },
  {
    id: 'data',
    label: '数据',
    accent: '#c2410c',
    commands: [
      makeCommand('data', 'data plot', '波形', '显示采样波形', ['data', 'plot']),
      makeCommand('data', 'data samples', '采样', '查看采样数据', ['data', 'samples']),
      makeCommand('data', 'data print', '打印', '打印数据缓冲区', ['data', 'print']),
      makeCommand('data', 'data save', '保存', '保存数据缓冲区', ['data', 'save']),
      makeCommand('data', 'data load', '载入', '载入数据文件', ['data', 'load']),
      makeCommand('data', 'data clear', '清空', '清空数据缓冲区', ['data', 'clear']),
      makeCommand('data', 'data askedge', 'ASK 边沿', 'ASK 边沿检测', ['data', 'ask']),
      makeCommand('data', 'data detectclock', '时钟', '检测信号时钟', ['data', 'clock']),
    ],
  },
  {
    id: 'scripts',
    label: '脚本',
    accent: '#0891b2',
    commands: [
      makeCommand('scripts', 'script list', '列表', '脚本列表', ['script', 'list']),
      makeCommand('scripts', 'script run', '运行', '运行脚本', ['script', 'run'], 'advanced'),
      makeCommand('scripts', 'script help', '帮助', '脚本帮助', ['script', 'help']),
      makeCommand('scripts', 'prefs show', '偏好', '客户端偏好设置', ['prefs']),
      makeCommand('scripts', 'prefs set', '设置', '修改客户端偏好', ['prefs', 'set'], 'advanced'),
    ],
  },
  {
    id: 'security',
    label: '分析',
    accent: '#be123c',
    commands: [
      makeCommand('security', 'hf mf darkside', 'Darkside 分析', 'MIFARE Classic Darkside 分析', ['attack', 'mf'], 'advanced'),
      makeCommand('security', 'hf mf staticnested', '静态嵌套分析', 'MIFARE Classic 静态嵌套分析', ['attack', 'mf'], 'advanced'),
      makeCommand('security', 'hf mf csetuid', 'UID 写入', 'Magic 卡 UID 写入', ['magic', 'uid'], 'write'),
      makeCommand('security', 'hf mf cwipe', '清卡', 'Magic 卡清空', ['magic', 'wipe'], 'write'),
      makeCommand('security', 'hf mf gen3uid', '三代卡 UID', '三代魔术卡 UID 写入', ['magic', 'gen3'], 'write'),
      makeCommand('security', 'hf 14a sniff', '14A 嗅探', 'ISO14443A 嗅探', ['sniff', '14a']),
      makeCommand('security', 'hf list', 'HF 记录', 'HF 通信记录', ['trace']),
      makeCommand('security', 'lf sniff', 'LF 嗅探', 'LF 通信嗅探', ['sniff', 'lf']),
    ],
  },
]

const groupByRoot: Record<string, CommandGroupId> = {
  analyse: 'discovered',
  data: 'data',
  emv: 'discovered',
  hf: 'hf',
  hw: 'device',
  lf: 'lf',
  mem: 'device',
  mqtt: 'discovered',
  nfc: 'discovered',
  piv: 'discovered',
  prefs: 'settings',
  reveng: 'discovered',
  script: 'scripts',
  smart: 'discovered',
  trace: 'discovered',
  wiegand: 'discovered',
}

export const catalogRoots = [
  'analyse',
  'data',
  'emv',
  'hf',
  'hw',
  'lf',
  'mqtt',
  'nfc',
  'piv',
  'prefs',
  'reveng',
  'script',
  'smart',
  'trace',
  'wiegand',
]

export const allBuiltinCommands = commandGroups.flatMap((group) => group.commands)

export const groupOptions = [
  { id: 'all' as CommandGroupId, label: '全部' },
  ...commandGroups.map((group) => ({ id: group.id, label: group.label })),
  { id: 'settings' as CommandGroupId, label: '设置' },
  { id: 'discovered' as CommandGroupId, label: '同步' },
]

const ansiColorPattern = new RegExp(`${String.fromCharCode(27)}\\[[0-9;]*m`, 'g')

const rootLabels: Record<string, string> = {
  analyse: '分析工具',
  data: '数据与波形',
  emv: '银行卡/EMV',
  help: '帮助',
  hf: '高频功能',
  hw: '设备硬件',
  lf: '低频功能',
  mem: '设备内存',
  mqtt: '消息联动',
  nfc: 'NFC 功能',
  piv: 'PIV 智能卡',
  prefs: '偏好设置',
  reveng: 'CRC 计算',
  script: '脚本',
  smart: '智能卡',
  trace: '通信记录',
  wiegand: '韦根格式',
}

const actionLabels: Record<string, string> = {
  chk: '检查密钥',
  clear: '清空',
  clone: '写卡/克隆',
  config: '配置',
  detect: '检测',
  detectclock: '检测时钟',
  dump: '导出数据',
  help: '帮助',
  info: '读取信息',
  list: '查看记录',
  load: '载入',
  ping: '通信测试',
  plot: '查看波形',
  print: '打印数据',
  read: '读取',
  reader: '读取',
  reset: '重启',
  restore: '写回数据',
  run: '运行',
  samples: '查看采样',
  save: '保存',
  search: '自动识别',
  set: '设置',
  show: '查看',
  sim: '模拟',
  sniff: '嗅探',
  status: '状态',
  tune: '天线检查',
  version: '版本信息',
  wipe: '清空卡片',
  write: '写入',
}

const exactLabels: Record<string, string> = {
  'hf mf autopwn': '自动分析 MIFARE',
  'hf mf darkside': 'Darkside 分析',
  'hf mf hardnested': '强化嵌套分析',
  'hf mf nested': '嵌套分析',
  'hf mf staticnested': '静态嵌套分析',
  'hf mf csetuid': '写入 UID',
  'hf mf cwipe': '清空魔术卡',
  'hf mf gen3uid': '三代卡 UID',
  'lf em 410x_clone': '克隆 EM410x',
  'lf em 410x_read': '读取 EM410x',
  'lf hid clone': '克隆 HID',
  'lf hid read': '读取 HID',
  'lf t55xx detect': '检测 T55xx',
}

function titleForCommand(command: string) {
  if (exactLabels[command]) {
    return exactLabels[command]
  }

  const parts = command.split(' ')
  const last = parts.at(-1) ?? command
  const root = parts[0]
  const action = actionLabels[last] ?? actionLabels[last.replace(/.*_/, '')]

  if (action && rootLabels[root]) {
    return `${action} · ${rootLabels[root]}`
  }

  return rootLabels[command] ?? rootLabels[root] ?? last.replace(/_/g, ' ')
}

function translateHelpSummary(command: string, summary: string) {
  const lower = summary.toLowerCase()
  const root = command.split(' ')[0]

  if (lower.includes('edit client') || lower.includes('preferences')) {
    return '管理客户端和设备偏好设置'
  }
  if (lower.includes('high frequency')) {
    return '高频卡相关功能，常见于 13.56MHz 卡片'
  }
  if (lower.includes('low frequency')) {
    return '低频卡相关功能，常见于 125kHz 门禁卡'
  }
  if (lower.includes('hardware')) {
    return '读取设备状态、版本、天线和通信信息'
  }
  if (lower.includes('plot') || lower.includes('data buffer')) {
    return '查看、保存或分析采样数据'
  }
  if (lower.includes('trace')) {
    return '查看或处理读卡通信记录'
  }
  if (lower.includes('script')) {
    return '运行官方客户端脚本'
  }
  if (lower.includes('crc')) {
    return '计算和分析 CRC 校验'
  }
  if (lower.includes('smart card')) {
    return '智能卡相关读取和分析'
  }
  if (lower.includes('write') || lower.includes('clone') || lower.includes('restore') || lower.includes('wipe')) {
    return '会修改卡片或设备数据，操作前请确认目标卡片'
  }
  if (lower.includes('read') || lower.includes('reader') || lower.includes('search') || lower.includes('detect')) {
    return '读取或识别卡片/信号信息'
  }
  if (rootLabels[root]) {
    return `${rootLabels[root]}：${summary.replace(/[{}]/g, '').trim()}`
  }

  return summary.replace(/[{}]/g, '').trim()
}

export function dedupeCommands(commands: Pm3Command[]): Pm3Command[] {
  const byCommand = new Map<string, Pm3Command>()

  for (const command of commands) {
    const key = command.command.trim().replace(/\s+/g, ' ').toLowerCase()
    if (!byCommand.has(key)) {
      byCommand.set(key, {
        ...command,
        command: command.command.trim().replace(/\s+/g, ' '),
      })
    }
  }

  return [...byCommand.values()]
}

export function parseHelpOutput(rawOutput: string, sourcePrefix = ''): Pm3Command[] {
  const lines = rawOutput.split(/\r?\n/)
  const parsed: Pm3Command[] = []

  for (const line of lines) {
    const clean = line
      .replace(ansiColorPattern, '')
      .replace(/^\[[=+!*#-]\]\s*/, '')
      .trimEnd()

    if (!clean.trim() || clean.includes('Proxmark') || clean.includes('usage:')) {
      continue
    }

    const match = clean.match(/^([a-z][a-z0-9_-]*(?:\s+[a-z0-9][a-z0-9_-]*){0,3})\s{2,}(.+)$/i)
    if (!match) {
      continue
    }

    const rawCommand = match[1].trim().toLowerCase()
    const summary = match[2].trim()

    if (rawCommand.length > 42 || summary.length < 2) {
      continue
    }

    const normalized = sourcePrefix && !rawCommand.startsWith(sourcePrefix)
      ? `${sourcePrefix} ${rawCommand}`
      : rawCommand
    const root = normalized.split(' ')[0]
    const groupId = groupByRoot[root] ?? 'discovered'
    const label = titleForCommand(normalized)

    parsed.push({
      id: `discovered:${normalized}`,
      groupId,
      label,
      command: normalized,
      description: translateHelpSummary(normalized, summary),
      tags: [root, 'synced'],
      source: 'discovered',
      risk: summary.toLowerCase().match(/write|clone|restore|wipe|flash/) ? 'write' : 'normal',
    })
  }

  return dedupeCommands(parsed)
}

export function filterCommands(commands: Pm3Command[], groupId: CommandGroupId, query: string) {
  const needle = query.trim().toLowerCase()

  return commands.filter((command) => {
    const groupMatches =
      groupId === 'all' ||
      command.groupId === groupId ||
      (groupId === 'discovered' && command.source === 'discovered')

    if (!groupMatches) {
      return false
    }

    if (!needle) {
      return true
    }

    return [
      command.label,
      command.command,
      command.description,
      ...command.tags,
    ].some((part) => part.toLowerCase().includes(needle))
  })
}
