import { useEffect, useMemo, useState } from 'react'
import type { LucideIcon } from 'lucide-react'
import {
  AlertTriangle,
  BadgeCheck,
  BookOpen,
  Braces,
  Cable,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  Cpu,
  Database,
  FileCode2,
  Fingerprint,
  Gauge,
  Layers3,
  ListFilter,
  Loader2,
  Play,
  Radio,
  RefreshCcw,
  Search,
  Settings,
  ShieldAlert,
  SquareTerminal,
  Usb,
  Zap,
} from 'lucide-react'
import './App.css'
import {
  allBuiltinCommands,
  catalogRoots,
  dedupeCommands,
  filterCommands,
  groupOptions,
  parseHelpOutput,
  type CommandGroupId,
  type CommandRisk,
  type Pm3Command,
} from './lib/commandCatalog'
import {
  detectPm3Binary,
  listSerialPorts,
  runPm3Command,
  runtimeLabel,
  type Pm3BinaryStatus,
  type SerialPortInfo,
} from './lib/pm3Bridge'

type LogEntry = {
  id: number
  kind: 'input' | 'output' | 'error' | 'system'
  text: string
}

type AppView = 'workbench' | 'tools' | 'console'
type DeviceHealth = 'ready' | 'seen' | 'missing' | 'error'

type WorkflowAction = {
  label: string
  command?: string
  view?: AppView
  tone?: 'primary' | 'secondary' | 'danger'
  hint?: string
}

type OperationGroup = {
  id: string
  title: string
  summary: string
  icon: LucideIcon
  tone: 'blue' | 'green' | 'amber' | 'red' | 'slate'
  actions: WorkflowAction[]
}

type CardSnapshot = {
  title: string
  uid: string
  cardType: string
  frequency: string
  note: string
  rows: string[]
}

const groupIcon = {
  all: ListFilter,
  device: Cpu,
  hf: Radio,
  lf: Zap,
  mifare: Fingerprint,
  data: Database,
  scripts: FileCode2,
  security: ShieldAlert,
  settings: Settings,
  discovered: Layers3,
} satisfies Record<CommandGroupId, LucideIcon>

const mainNav: Array<{ id: AppView; label: string; hint: string; icon: LucideIcon }> = [
  { id: 'workbench', label: '操作台', hint: '像常规软件一样点按钮', icon: Layers3 },
  { id: 'tools', label: '功能库', hint: '只读诊断入口', icon: BookOpen },
  { id: 'console', label: '高级命令', hint: '后端白名单限制', icon: SquareTerminal },
]

const quickCommands: WorkflowAction[] = [
  { label: '读取设备版本', command: 'hw version', tone: 'primary', hint: '先确认 PM3 能否回应' },
  { label: '高频识别', command: 'hf search', hint: '门禁 IC 卡、NFC 卡常用' },
  { label: '低频识别', command: 'lf search', hint: '125k 门禁卡常用' },
  { label: '天线检查', command: 'hw tune', hint: '看天线是否正常' },
]

const modeChips: WorkflowAction[] = [
  { label: '13.56M 高频卡', command: 'hf search', hint: 'IC 卡、MIFARE、NFC' },
  { label: '125k 低频卡', command: 'lf search', hint: 'ID 门禁、HID、EM' },
  { label: 'MIFARE 常用', command: 'hf mf info', hint: '先读信息，再分析密钥' },
  { label: '查看通信记录', command: 'hf list', hint: '看刚才交互过程' },
]

const operationGroups: OperationGroup[] = [
  {
    id: 'identify',
    title: '读卡识别',
    summary: '不知道卡是什么类型时，从这里开始。',
    icon: Search,
    tone: 'blue',
    actions: [
      { label: '自动识别高频卡', command: 'hf search', tone: 'primary' },
      { label: '自动识别低频卡', command: 'lf search' },
      { label: '读取 14A 信息', command: 'hf 14a info' },
      { label: '读取 MIFARE 信息', command: 'hf mf info' },
    ],
  },
  {
    id: 'mifare',
    title: 'MIFARE 卡',
    summary: '小区门禁、车位卡常见。先查信息，再看密钥。',
    icon: Fingerprint,
    tone: 'green',
    actions: [
      { label: '检查默认密钥', command: 'hf mf chk', tone: 'primary' },
      { label: '自动分析整卡', command: 'hf mf autopwn' },
      { label: '导出卡片数据', command: 'hf mf dump' },
      { label: '查看高频记录', command: 'hf list' },
    ],
  },
  {
    id: 'low',
    title: '低频门禁',
    summary: 'ID 卡、HID、EM410x、T55xx 先从这里试。',
    icon: Zap,
    tone: 'amber',
    actions: [
      { label: '读取 HID', command: 'lf hid read', tone: 'primary' },
      { label: '读取 EM410x', command: 'lf em 410x_read' },
      { label: '检测 T55xx', command: 'lf t55xx detect' },
      { label: '采样低频信号', command: 'lf read' },
    ],
  },
  {
    id: 'device',
    title: '设备检查',
    summary: '确认 PM3、USB、天线和内核是否匹配。',
    icon: Gauge,
    tone: 'slate',
    actions: [
      { label: '读取设备版本', command: 'hw version', tone: 'primary' },
      { label: '测试通信', command: 'hw ping' },
      { label: '设备状态', command: 'hw status' },
      { label: '检查天线', command: 'hw tune' },
    ],
  },
  {
    id: 'data',
    title: '数据与波形',
    summary: '识别不出来时，看原始信号和通信记录。',
    icon: Database,
    tone: 'blue',
    actions: [
      { label: '查看波形', command: 'data plot', tone: 'primary' },
      { label: '查看采样', command: 'data samples' },
      { label: '保存采样', command: 'data save' },
      { label: '清空缓存', command: 'data clear' },
    ],
  },
  {
    id: 'write',
    title: '写卡与模拟（已冻结）',
    summary: '实验原型不提供这些操作，按钮和 Rust 后端均已禁用。',
    icon: ShieldAlert,
    tone: 'red',
    actions: [
      { label: 'MIFARE 写回', command: 'hf mf restore', tone: 'danger' },
      { label: 'UID 写入', command: 'hf mf csetuid', tone: 'danger' },
      { label: 'HID 写卡', command: 'lf hid clone', tone: 'danger' },
      { label: 'T55xx 写入', command: 'lf t55xx write', tone: 'danger' },
    ],
  },
]

const placeholderRows = [
  '00/0  等待读取卡片数据',
  '00/1  读取成功后这里显示关键块',
  '00/2  不需要先理解命令行',
  '00/3  可从左侧按钮开始操作',
]

const ansiPattern = new RegExp(`${String.fromCharCode(27)}\\[[0-9;]*m`, 'g')

function App() {
  const [ports, setPorts] = useState<SerialPortInfo[]>([])
  const [selectedPort, setSelectedPort] = useState('')
  const [binaryPath, setBinaryPath] = useState('')
  const [binaryStatus, setBinaryStatus] = useState<Pm3BinaryStatus | null>(null)
  const [activeView, setActiveView] = useState<AppView>('workbench')
  const [activeGroup, setActiveGroup] = useState<CommandGroupId>('all')
  const [query, setQuery] = useState('')
  const [commandInput, setCommandInput] = useState('hw version')
  const [isBusy, setIsBusy] = useState(false)
  const [discoveredCommands, setDiscoveredCommands] = useState<Pm3Command[]>([])
  const [deviceHealth, setDeviceHealth] = useState<DeviceHealth>('missing')
  const [deviceVersion, setDeviceVersion] = useState('未读取')
  const [deviceDetails, setDeviceDetails] = useState<string[]>([])
  const [lastChecked, setLastChecked] = useState('尚未检测')
  const [lastResult, setLastResult] = useState('等待操作')
  const [runningText, setRunningText] = useState('')
  const [cardSnapshot, setCardSnapshot] = useState<CardSnapshot | null>(null)
  const [logs, setLogs] = useState<LogEntry[]>([
    { id: 1, kind: 'system', text: 'React/Tauri 实验原型仅供开发验证，禁止发布。当前只允许后端白名单内的只读诊断命令。' },
  ])

  const mergedCommands = useMemo(
    () => dedupeCommands([...allBuiltinCommands, ...discoveredCommands]),
    [discoveredCommands],
  )

  const visibleCommands = useMemo(
    () => filterCommands(mergedCommands, activeGroup, query),
    [activeGroup, mergedCommands, query],
  )

  const selectedPortInfo = ports.find((port) => port.path === selectedPort)
  const deviceName = selectedPortInfo?.likelyPm3
    ? '疑似 Proxmark3'
    : selectedPortInfo?.kind ?? '未选择设备'
  const clientVersion = compactClientVersion(binaryStatus?.version)
  const connectionTitle = connectionText(deviceHealth, selectedPort, ports.length)
  const connectionTone = deviceHealth === 'ready' ? 'ok' : deviceHealth === 'error' ? 'bad' : 'warn'
  const binaryTone = binaryStatus?.found ? 'ok' : 'bad'

  useEffect(() => {
    async function loadInitialEnvironment() {
      try {
        const [nextPorts, nextStatus] = await Promise.all([
          listSerialPorts(),
          detectPm3Binary(),
        ])

        setPorts(nextPorts)
        setBinaryStatus(nextStatus)
        setLastChecked(timeLabel())

        const pm3Port = nextPorts.find((port) => port.likelyPm3)
        if (pm3Port) {
          setSelectedPort((current) => current || pm3Port.path)
          setDeviceHealth(pm3Port.likelyPm3 ? 'seen' : 'missing')
        } else {
          setDeviceHealth('missing')
        }

        if (nextStatus.path) {
          setBinaryPath((current) => current || nextStatus.path || '')
        }
      } catch (error) {
        setDeviceHealth('error')
        appendLog('error', friendlyError(error))
      }
    }

    void loadInitialEnvironment()
  }, [])

  function appendLog(kind: LogEntry['kind'], text: string) {
    setLogs((current) => [
      ...current.slice(-240),
      {
        id: Date.now() + Math.random(),
        kind,
        text: text.trimEnd(),
      },
    ])
  }

  function selectPort(nextPort: string) {
    if (nextPort === selectedPort) {
      return
    }

    const portInfo = ports.find((port) => port.path === nextPort)
    setSelectedPort(nextPort)
    setDeviceHealth(portInfo?.likelyPm3 ? 'seen' : 'missing')
    setDeviceVersion('未读取')
    setDeviceDetails([])
    setLastChecked('尚未检测')
    setLastResult(nextPort ? '设备口已切换，请重新读取设备版本' : '尚未选择设备口')
  }

  async function refreshEnvironment() {
    try {
      const [nextPorts, nextStatus] = await Promise.all([
        listSerialPorts(),
        detectPm3Binary(binaryPath.trim() || undefined),
      ])

      setPorts(nextPorts)
      setBinaryStatus(nextStatus)
      setLastChecked(timeLabel())

      const pm3Port = nextPorts.find((port) => port.likelyPm3)
      const currentPort = nextPorts.find((port) => port.path === selectedPort)
      const nextPort = currentPort ?? pm3Port
      const selectionChanged = (nextPort?.path ?? '') !== selectedPort

      if (selectionChanged) {
        setSelectedPort(nextPort?.path ?? '')
        setDeviceVersion('未读取')
        setDeviceDetails([])
        setLastChecked('尚未检测')
        setLastResult(nextPort ? '设备列表已变化，请重新读取设备版本' : '尚未选择设备口')
      }
      setDeviceHealth((current) =>
        !selectionChanged && current === 'ready'
          ? 'ready'
          : nextPort?.likelyPm3 ? 'seen' : 'missing',
      )

      if (nextStatus.path && !binaryPath) {
        setBinaryPath(nextStatus.path)
      }

      appendLog('system', '已重新检测设备和官方内核。')
    } catch (error) {
      setDeviceHealth('error')
      appendLog('error', friendlyError(error))
    }
  }

  async function executeCommand(commandOverride?: string) {
    const command = (commandOverride ?? commandInput).trim()
    if (!command || isBusy) {
      return
    }

    setCommandInput(command)
    const freezeMessage = prototypeFreezeMessage(command)
    if (freezeMessage) {
      setLastResult(freezeMessage)
      appendLog('error', freezeMessage)
      return
    }

    const helpCommand = isHelpCommand(command)
    const preflightMessage = commandPreflightMessage({
      command,
      helpCommand,
      selectedPort,
      binaryFound: Boolean(binaryStatus?.found),
      binaryPath,
      deviceHealth,
    })

    if (preflightMessage) {
      setLastResult(preflightMessage)
      appendLog('error', preflightMessage)
      return
    }

    const timeoutMs = timeoutForCommand(command, helpCommand)
    const commandName = friendlyCommandName(command, mergedCommands)

    setIsBusy(true)
    setRunningText(`正在执行：${commandName}，最多等待 ${timeoutLabel(timeoutMs)}`)
    setLastResult(`正在执行：${commandName}`)
    appendLog('input', `准备执行：${commandName}\n底层命令：${command}\n本次最多等待：${timeoutLabel(timeoutMs)}`)

    try {
      const result = await runPm3Command({
        binaryPath: binaryPath.trim() || undefined,
        port: helpCommand ? undefined : selectedPort || undefined,
        command,
        offline: helpCommand,
        timeoutMs,
      })

      const summaries = explainResult(command, result.ok, result.stdout, result.stderr)
      for (const summary of summaries) {
        appendLog(result.ok ? 'system' : 'error', summary)
      }
      setLastResult(summaries[0] ?? (result.ok ? '命令已完成' : '命令执行失败'))

      if (result.stdout.trim()) {
        appendLog('output', `原始输出：\n${result.stdout}`)
      }
      if (result.stderr.trim()) {
        appendLog(result.ok ? 'output' : 'error', `错误信息：\n${result.stderr}`)
      }
      if (!result.ok) {
        appendLog('error', `退出码：${result.status ?? '未知'}`)
      }

      if (result.ok) {
        const nextSnapshot = parseCardSnapshot(command, result.stdout)
        if (nextSnapshot) {
          setCardSnapshot(nextSnapshot)
        }
      }

      if (command === 'hw version') {
        setLastChecked(timeLabel())
        if (result.ok) {
          const parsed = parseDeviceVersion(result.stdout)
          setDeviceHealth('ready')
          setDeviceVersion(parsed.summary)
          setDeviceDetails(parsed.details)
        } else {
          setDeviceHealth('error')
          setDeviceVersion('读取失败')
          setDeviceDetails(['电脑能看到串口，但 PM3 没有回应。'])
        }
      } else if (!helpCommand && !result.ok && result.stderr.toLowerCase().includes('cannot communicate')) {
        setDeviceHealth('error')
        setLastChecked(timeLabel())
      }

      if (command === 'help' || command.endsWith(' help')) {
        const prefix = command.endsWith(' help') ? command.replace(/\s+help$/, '') : ''
        setDiscoveredCommands((current) =>
          dedupeCommands([...current, ...parseHelpOutput(result.stdout, prefix)]),
        )
      }
    } catch (error) {
      setLastResult('命令没有成功执行')
      appendLog('error', friendlyError(error))
    } finally {
      setIsBusy(false)
      setRunningText('')
    }
  }

  async function syncCommandCatalog() {
    if (isBusy) {
      return
    }

    setIsBusy(true)
    appendLog('system', '正在从官方 PM3 内核同步功能目录。这个过程不需要设备通信。')

    try {
      const collected: Pm3Command[] = []
      const rootHelp = await runPm3Command({
        binaryPath: binaryPath.trim() || undefined,
        command: 'help',
        offline: true,
        timeoutMs: 120000,
      })

      collected.push(...parseHelpOutput(rootHelp.stdout))

      for (const root of catalogRoots) {
        const response = await runPm3Command({
          binaryPath: binaryPath.trim() || undefined,
          command: `${root} help`,
          offline: true,
          timeoutMs: 120000,
        })
        collected.push(...parseHelpOutput(response.stdout, root))
      }

      const nextCommands = dedupeCommands(collected)
      setDiscoveredCommands(nextCommands)
      setLastResult(`已同步 ${nextCommands.length} 个官方功能入口`)
      appendLog('system', `已同步 ${nextCommands.length} 个官方功能入口，并完成中文整理。`)
    } catch (error) {
      appendLog('error', friendlyError(error))
    } finally {
      setIsBusy(false)
    }
  }

  function pickCommand(command: Pm3Command) {
    setCommandInput(command.command)
    setActiveView('console')
  }

  function runAction(action: WorkflowAction) {
    if (action.view) {
      setActiveView(action.view)
      return
    }

    if (action.command) {
      void executeCommand(action.command)
    }
  }

  return (
    <main className="app-shell">
      <header className="mac-toolbar">
        <div className="window-dots" aria-hidden="true">
          <span className="dot red" />
          <span className="dot amber" />
          <span className="dot green" />
        </div>

        <div className="brand">
          <div className="brand-mark">
            <Cable aria-hidden="true" size={20} />
          </div>
          <div>
            <h1>PM3 中文助手 · 实验原型</h1>
            <span>冻结的 React/Tauri 验证分支 · {runtimeLabel()}</span>
          </div>
        </div>

        <div className="connection-strip">
          <label className="field compact">
            <span>设备口</span>
            <select value={selectedPort} onChange={(event) => selectPort(event.target.value)}>
              <option value="">未选择</option>
              {ports.map((port) => (
                <option key={port.path} value={port.path}>
                  {port.path} · {port.kind}
                </option>
              ))}
            </select>
          </label>

          <label className="field binary-field">
            <span>PM3 内核</span>
            <input
              value={binaryPath}
              readOnly
              aria-readonly="true"
              title="仅由后端从受信任位置选择 PM3 内核"
              placeholder="由后端从受信任位置自动选择"
            />
          </label>

          <button className="icon-button" type="button" onClick={refreshEnvironment} title="重新检测">
            <RefreshCcw size={18} aria-hidden="true" />
          </button>
        </div>
      </header>

      <section className="experimental-banner" role="alert">
        <AlertTriangle size={17} aria-hidden="true" />
        <strong>实验原型 · 禁止发布</strong>
        <span>仅供开发验证；写卡、模拟、擦除、刷写、脚本执行及未知命令已被 Rust 后端默认拒绝。正式功能请使用 QML 主客户端。</span>
      </section>

      <section className="device-statusbar" aria-label="设备状态栏">
        <StatusItem
          icon={Usb}
          tone={connectionTone}
          title="连接"
          value={connectionTitle}
          detail={selectedPort || '没有检测到可用串口'}
        />
        <StatusItem
          icon={Cpu}
          tone={selectedPortInfo?.likelyPm3 ? 'ok' : selectedPort ? 'warn' : 'bad'}
          title="设备"
          value={deviceName}
          detail={selectedPortInfo?.likelyPm3 ? '系统识别为 Proxmark3 类设备' : '需要选择 PM3 串口'}
        />
        <StatusItem
          icon={BadgeCheck}
          tone={binaryTone}
          title="内核"
          value={binaryStatus?.found ? '已找到' : '未找到'}
          detail={clientVersion || binaryStatus?.error || '等待检测'}
        />
        <StatusItem
          icon={Gauge}
          tone={deviceHealth === 'ready' ? 'ok' : deviceHealth === 'error' ? 'bad' : 'warn'}
          title="版本"
          value={deviceVersion}
          detail={deviceDetails[0] || `最后检测：${lastChecked}`}
        />
      </section>

      <nav className="view-tabs" aria-label="主功能">
        {mainNav.map((item) => {
          const Icon = item.icon
          return (
            <button
              key={item.id}
              type="button"
              className={activeView === item.id ? 'view-tab active' : 'view-tab'}
              onClick={() => setActiveView(item.id)}
            >
              <Icon size={16} aria-hidden="true" />
              <span>{item.label}</span>
              <small>{item.hint}</small>
            </button>
          )
        })}
      </nav>

      <section className="main-panel">
        {activeView === 'workbench' && (
          <WorkbenchView
            cardSnapshot={cardSnapshot}
            deviceHealth={deviceHealth}
            isBusy={isBusy}
            lastResult={lastResult}
            onOpenTools={() => setActiveView('tools')}
            onRunAction={runAction}
          />
        )}

        {activeView === 'tools' && (
          <ToolsView
            activeGroup={activeGroup}
            query={query}
            commands={visibleCommands}
            totalCommands={mergedCommands.length}
            isBusy={isBusy}
            onGroupChange={setActiveGroup}
            onQueryChange={setQuery}
            onSync={syncCommandCatalog}
            onPick={pickCommand}
            onRun={(command) => void executeCommand(command)}
          />
        )}

        {activeView === 'console' && (
          <ManualConsoleView
            commandInput={commandInput}
            isBusy={isBusy}
            onCommandChange={setCommandInput}
            onRun={() => void executeCommand()}
          />
        )}
      </section>

      <section className="console-panel">
        <div className="console-head">
          <div>
            <SquareTerminal size={18} aria-hidden="true" />
            <span>执行记录</span>
          </div>
          <span className={isBusy ? 'running-status' : undefined}>{runningText || lastResult}</span>
        </div>

        <div className="terminal" aria-live="polite">
          {logs.map((entry) => (
            <pre key={entry.id} className={`log-line ${entry.kind}`}>{entry.text}</pre>
          ))}
        </div>

        <form
          className="command-form"
          onSubmit={(event) => {
            event.preventDefault()
            void executeCommand()
          }}
        >
          <input value={commandInput} onChange={(event) => setCommandInput(event.target.value)} placeholder="输入底层 PM3 命令，例：hw version" />
          <button type="submit" disabled={isBusy}>
            {isBusy ? <Loader2 className="spin" size={18} aria-hidden="true" /> : <Play size={18} aria-hidden="true" />}
            <span>执行</span>
          </button>
        </form>
      </section>
    </main>
  )
}

function WorkbenchView({
  cardSnapshot,
  deviceHealth,
  isBusy,
  lastResult,
  onOpenTools,
  onRunAction,
}: {
  cardSnapshot: CardSnapshot | null
  deviceHealth: DeviceHealth
  isBusy: boolean
  lastResult: string
  onOpenTools: () => void
  onRunAction: (action: WorkflowAction) => void
}) {
  const advice = deviceAdvice(deviceHealth)
  const AdviceIcon = advice.icon

  return (
    <div className="workbench-view">
      <aside className="left-rail">
        <section className={`assistant-panel ${advice.tone}`}>
          <div className="assistant-head">
            <AdviceIcon size={20} aria-hidden="true" />
            <div>
              <h2>{advice.title}</h2>
              <p>{advice.detail}</p>
            </div>
          </div>
          <strong>{lastResult}</strong>
        </section>

        <section className="quick-panel">
          <h2>新手顺序</h2>
          <div className="quick-list">
            {quickCommands.map((action, index) => (
              <button key={action.label} type="button" onClick={() => onRunAction(action)} disabled={isBusy}>
                <span className="step-index">{index + 1}</span>
                <span>
                  <strong>{action.label}</strong>
                  <small>{action.hint}</small>
                </span>
              </button>
            ))}
          </div>
        </section>

        <section className="mode-panel">
          <h2>卡片类型</h2>
          <div className="mode-list">
            {modeChips.map((action) => (
              <button key={action.label} type="button" onClick={() => onRunAction(action)} disabled={isBusy}>
                <span>{action.label}</span>
                <small>{action.hint}</small>
              </button>
            ))}
          </div>
        </section>
      </aside>

      <section className="center-board">
        <div className="board-head">
          <div>
            <h2>常用操作</h2>
            <p>这些按钮背后还是官方 PM3 命令，只是换成更容易理解的中文动作。</p>
          </div>
          <button className="tool-button" type="button" onClick={onOpenTools}>
            <Layers3 size={17} aria-hidden="true" />
            <span>全部功能</span>
          </button>
        </div>

        <div className="operation-grid">
          {operationGroups.map((group) => (
            <OperationPanel
              key={group.id}
              group={group}
              isBusy={isBusy}
              onRunAction={onRunAction}
            />
          ))}
        </div>
      </section>

      <aside className="right-rail">
        <CardPreview snapshot={cardSnapshot} />
        <SafetyPanel />
      </aside>
    </div>
  )
}

function OperationPanel({
  group,
  isBusy,
  onRunAction,
}: {
  group: OperationGroup
  isBusy: boolean
  onRunAction: (action: WorkflowAction) => void
}) {
  const Icon = group.icon

  return (
    <section className={`operation-panel tone-${group.tone}`}>
      <div className="operation-head">
        <div className="operation-icon">
          <Icon size={19} aria-hidden="true" />
        </div>
        <div>
          <h3>{group.title}</h3>
          <p>{group.summary}</p>
        </div>
      </div>
      <div className="button-grid">
        {group.actions.map((action) => (
          <button
            key={action.label}
            className={`operation-button ${action.tone ?? 'secondary'}`}
            type="button"
            disabled={isBusy || action.tone === 'danger'}
            title={action.tone === 'danger' ? '实验原型已冻结写卡与模拟功能' : undefined}
            onClick={() => onRunAction(action)}
          >
            <span>{action.label}</span>
            {action.tone === 'danger' ? <ShieldAlert size={14} aria-hidden="true" /> : <ChevronRight size={14} aria-hidden="true" />}
          </button>
        ))}
      </div>
    </section>
  )
}

function CardPreview({ snapshot }: { snapshot: CardSnapshot | null }) {
  const rows = snapshot?.rows.length ? snapshot.rows : placeholderRows

  return (
    <section className="card-preview">
      <div className="panel-title">
        <div>
          <span>卡片数据</span>
          <h2>{snapshot?.title ?? '等待读卡'}</h2>
        </div>
        <Fingerprint size={20} aria-hidden="true" />
      </div>

      <div className="card-facts">
        <InfoPair label="UID / 卡号" value={snapshot?.uid ?? '待读取'} />
        <InfoPair label="卡片类型" value={snapshot?.cardType ?? '未知'} />
        <InfoPair label="频率" value={snapshot?.frequency ?? '未判断'} />
      </div>

      <div className="memory-panel">
        <div className="memory-head">
          <span>数据块预览</span>
          <small>读取成功后自动更新</small>
        </div>
        <div className="memory-rows">
          {rows.map((row, index) => (
            <code key={`${row}-${index}`}>{row}</code>
          ))}
        </div>
      </div>

      <p>{snapshot?.note ?? '先把卡放到天线附近，然后点左侧「高频识别」或「低频识别」。'}</p>
    </section>
  )
}

function InfoPair({ label, value }: { label: string; value: string }) {
  return (
    <div className="info-pair">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function SafetyPanel() {
  return (
    <section className="safety-panel">
      <div className="panel-title compact">
        <div>
          <span>操作提醒</span>
          <h2>只读冻结</h2>
        </div>
        <ShieldAlert size={19} aria-hidden="true" />
      </div>
      <ul>
        <li>此分支仅用于只读开发验证。</li>
        <li>写卡、模拟、清卡和刷固件已禁用。</li>
        <li>不得将 React/Tauri 原型作为发布版本。</li>
      </ul>
    </section>
  )
}

function ToolsView({
  activeGroup,
  query,
  commands,
  totalCommands,
  isBusy,
  onGroupChange,
  onQueryChange,
  onSync,
  onPick,
  onRun,
}: {
  activeGroup: CommandGroupId
  query: string
  commands: Pm3Command[]
  totalCommands: number
  isBusy: boolean
  onGroupChange: (group: CommandGroupId) => void
  onQueryChange: (query: string) => void
  onSync: () => void
  onPick: (command: Pm3Command) => void
  onRun: (command: string) => void
}) {
  return (
    <div className="tools-view">
      <div className="section-head">
        <div>
          <h2>功能库</h2>
          <p>这里只展示开发期入口；Rust 后端仅放行明确列出的只读诊断命令。</p>
        </div>
        <button className="tool-button" type="button" onClick={onSync} disabled={isBusy}>
          {isBusy ? <Loader2 className="spin" size={17} aria-hidden="true" /> : <RefreshCcw size={17} aria-hidden="true" />}
          <span>同步官方功能</span>
        </button>
      </div>

      <div className="command-toolbar">
        <label className="search-box">
          <Search size={18} aria-hidden="true" />
          <input value={query} onChange={(event) => onQueryChange(event.target.value)} placeholder="搜索功能，例如：高频、低频、MIFARE、天线" />
        </label>
        <span className="count-pill">{commands.length} / {totalCommands}</span>
      </div>

      <div className="group-tabs">
        {groupOptions.map((group) => {
          const Icon = groupIcon[group.id]
          return (
            <button
              key={group.id}
              className={activeGroup === group.id ? 'group-tab active' : 'group-tab'}
              type="button"
              onClick={() => onGroupChange(group.id)}
            >
              <Icon size={15} aria-hidden="true" />
              <span>{group.label}</span>
            </button>
          )
        })}
      </div>

      <div className="command-grid">
        {commands.map((command) => (
          <CommandTile
            key={command.id}
            command={command}
            onPick={onPick}
            onRun={onRun}
          />
        ))}
      </div>
    </div>
  )
}

function CommandTile({
  command,
  onPick,
  onRun,
}: {
  command: Pm3Command
  onPick: (command: Pm3Command) => void
  onRun: (command: string) => void
}) {
  const risk = command.risk ?? 'normal'

  return (
    <article className={`command-tile risk-${risk}`}>
      <div>
        <div className="tile-head">
          <span>{command.label}</span>
          <RiskBadge risk={risk} source={command.source} />
        </div>
        <p>{command.description}</p>
        <details>
          <summary>查看底层命令</summary>
          <code>{command.command}</code>
        </details>
      </div>
      <div className="tile-actions">
        <button type="button" className="ghost-button" onClick={() => onPick(command)} title="放到控制台">
          <Braces size={16} aria-hidden="true" />
        </button>
        <button
          type="button"
          className="run-button"
          onClick={() => onRun(command.command)}
          title={risk === 'write' ? '实验原型已禁用写操作' : '执行'}
          disabled={risk === 'write'}
        >
          <Play size={15} aria-hidden="true" />
        </button>
      </div>
    </article>
  )
}

function ManualConsoleView({
  commandInput,
  isBusy,
  onCommandChange,
  onRun,
}: {
  commandInput: string
  isBusy: boolean
  onCommandChange: (command: string) => void
  onRun: () => void
}) {
  return (
    <div className="manual-view">
      <section className="manual-panel">
        <div>
          <SquareTerminal size={24} aria-hidden="true" />
          <h2>高级命令</h2>
          <p>输入仍会经过 Rust 后端只读白名单；未知命令和所有写入、模拟、刷写命令都会被拒绝。</p>
        </div>
        <form
          className="manual-form"
          onSubmit={(event) => {
            event.preventDefault()
            onRun()
          }}
        >
          <input value={commandInput} onChange={(event) => onCommandChange(event.target.value)} placeholder="例如：hf search" />
          <button type="submit" disabled={isBusy}>
            {isBusy ? <Loader2 className="spin" size={18} aria-hidden="true" /> : <Play size={18} aria-hidden="true" />}
            <span>执行命令</span>
          </button>
        </form>
      </section>

      <section className="manual-tips">
        <h3>常见输入</h3>
        <button type="button" onClick={() => onCommandChange('hw version')}>读取设备版本</button>
        <button type="button" onClick={() => onCommandChange('hf search')}>识别高频卡</button>
        <button type="button" onClick={() => onCommandChange('lf search')}>识别低频卡</button>
        <button type="button" onClick={() => onCommandChange('hw tune')}>检查天线</button>
      </section>
    </div>
  )
}

function StatusItem({
  icon: Icon,
  tone,
  title,
  value,
  detail,
}: {
  icon: LucideIcon
  tone: 'ok' | 'warn' | 'bad'
  title: string
  value: string
  detail: string
}) {
  return (
    <article className={`status-card ${tone}`}>
      <div className="status-icon">
        <Icon size={18} aria-hidden="true" />
      </div>
      <div>
        <span>{title}</span>
        <strong>{value}</strong>
        <small>{detail}</small>
      </div>
    </article>
  )
}

function RiskBadge({ risk, source }: { risk: CommandRisk; source?: Pm3Command['source'] }) {
  if (risk === 'write') {
    return <small className="risk-badge write">会写入</small>
  }

  if (risk === 'advanced') {
    return <small className="risk-badge advanced">高级</small>
  }

  if (source === 'discovered') {
    return <small className="risk-badge synced">官方同步</small>
  }

  return <small className="risk-badge normal">常规</small>
}

function compactClientVersion(version?: string) {
  if (!version) {
    return ''
  }

  const line = version
    .split(/\r?\n/)
    .map((part) => part.trim())
    .find((part) => part.includes('Client:')) ?? version.trim()

  return line.replace(/^Client:\s*/, '').slice(0, 92)
}

function connectionText(health: DeviceHealth, selectedPort: string, portCount: number) {
  if (health === 'ready') {
    return '已通信'
  }
  if (health === 'error') {
    return '通信失败'
  }
  if (selectedPort) {
    return '已识别串口'
  }
  if (portCount > 0) {
    return '待选择设备'
  }
  return '未检测到设备'
}

function deviceAdvice(health: DeviceHealth): { title: string; detail: string; tone: string; icon: LucideIcon } {
  if (health === 'ready') {
    return {
      title: '设备已经能通信',
      detail: '可以开始识别卡片，或进入功能库选择更具体的操作。',
      tone: 'ok',
      icon: CheckCircle2,
    }
  }

  if (health === 'error') {
    return {
      title: '电脑看到设备，但 PM3 没有回应',
      detail: '先不要刷写。优先确认 Mac 端客户端是否和设备固件匹配。',
      tone: 'bad',
      icon: AlertTriangle,
    }
  }

  if (health === 'seen') {
    return {
      title: '已发现疑似 PM3 设备',
      detail: '下一步读取设备版本。成功后状态栏会显示固件信息。',
      tone: 'warn',
      icon: CircleHelp,
    }
  }

  return {
    title: '还没有发现 PM3 设备',
    detail: '插上设备后点右上角刷新。如果仍然没有出现，换 USB 线或接口再试。',
    tone: 'bad',
    icon: Cable,
  }
}

function friendlyCommandName(command: string, commands: Pm3Command[]) {
  return commands.find((item) => item.command === command)?.label ?? command
}

function isHelpCommand(command: string) {
  return command === 'help' || command.endsWith(' help')
}

function prototypeFreezeMessage(command: string) {
  const normalized = command.trim().toLowerCase().replace(/\s+/g, ' ')
  const tokens = normalized.split(' ')
  const mutating = tokens.some((token) =>
    [
      'bootloader',
      'clone',
      'csetuid',
      'cwipe',
      'emulate',
      'flash',
      'gen3uid',
      'restore',
      'sim',
      'simulate',
      'wipe',
      'wrbl',
      'write',
      'writeblk',
    ].some((marker) => token.includes(marker)),
  ) || ['script run', 'prefs set', 'hw reset'].some(
    (prefix) => normalized === prefix || normalized.startsWith(`${prefix} `),
  )

  return mutating
    ? 'React/Tauri 实验原型处于只读冻结状态，此操作不会执行。请使用 QML 主客户端的事务式写卡流程。'
    : ''
}

function isHealthCheckCommand(command: string) {
  return ['hw version', 'hw ping', 'hw status', 'hw tune'].includes(command)
}

function commandPreflightMessage({
  command,
  helpCommand,
  selectedPort,
  binaryFound,
  binaryPath,
  deviceHealth,
}: {
  command: string
  helpCommand: boolean
  selectedPort: string
  binaryFound: boolean
  binaryPath: string
  deviceHealth: DeviceHealth
}) {
  if (!binaryFound && !binaryPath.trim() && command !== 'hw version') {
    return '后端没有在受信任位置找到 PM3 内核。请确认 Homebrew 的 pm3/proxmark3 已安装。'
  }

  if (!helpCommand && !selectedPort) {
    return '还没有选择 PM3 设备。请先插上设备，或在顶部「设备口」里选择串口。'
  }

  if (!helpCommand && deviceHealth === 'error' && !isHealthCheckCommand(command)) {
    return '当前设备处于通信失败状态。为了避免反复等待串口超时，先执行「读取设备版本」或重新插拔设备后点刷新。'
  }

  return ''
}

function timeoutForCommand(command: string, helpCommand: boolean) {
  if (helpCommand) {
    return 120_000
  }

  if (['hw version', 'hw ping', 'hw status'].includes(command)) {
    return 8_000
  }

  if (command === 'hw tune') {
    return 12_000
  }

  if (command.endsWith(' search')) {
    return 45_000
  }

  if (/\b(dump|restore|write|clone|autopwn|nested|hardnested|sim|sniff)\b/.test(command)) {
    return 120_000
  }

  if (/\b(read|info|detect|chk|list|samples|plot)\b/.test(command)) {
    return 30_000
  }

  return 20_000
}

function timeoutLabel(timeoutMs: number) {
  const seconds = Math.round(timeoutMs / 1000)
  return seconds >= 60 ? `${Math.round(seconds / 60)} 分钟` : `${seconds} 秒`
}

function explainResult(command: string, ok: boolean, stdout: string, stderr: string) {
  const text = `${stdout}\n${stderr}`.toLowerCase()

  if (text.includes('cannot communicate')) {
    return [
      '通信失败：普通官方客户端没有收到回应。',
      '这台 PM3 Easy 已发现短回包特征；如果只是读取版本，请用「读取设备版本」确认兼容模式是否可用。',
    ]
  }

  if (text.includes('claimed by another process')) {
    return ['串口被其他程序占用。请关闭另一个 PM3 客户端或串口工具后再试。']
  }

  if (text.includes('invalid serial port')) {
    return ['串口不可用。请重新检测设备，优先选择 /dev/cu.usbmodem 开头的端口。']
  }

  if (text.includes('timed out') || text.includes('执行超时')) {
    return ['命令超时：设备或官方内核长时间没有返回结果。']
  }

  if (!ok) {
    return ['命令执行失败。可以在下方执行记录里查看原始输出。']
  }

  if (command === 'hw version') {
    if (text.includes('兼容模式') || text.includes('短回包')) {
      return ['设备版本读取完成：已使用 PM3 Easy 兼容模式，状态栏会同步显示关键信息。']
    }

    return ['设备版本读取完成。状态栏会同步显示关键信息。']
  }

  if (command.endsWith(' search')) {
    return ['识别流程已完成。若读到卡片，右侧会显示卡片线索。']
  }

  if (/\b(restore|write|clone|csetuid|cwipe)\b/.test(command)) {
    return ['写入类命令已结束。请核对下方原始输出确认是否真正写入成功。']
  }

  return ['命令已完成。']
}

function parseDeviceVersion(output: string) {
  const lines = output
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)

  const important = lines.filter((line) =>
    /client|bootrom|firmware|platform|device|os:|hardware|version|引导信息|固件信息|智能卡|fpga|兼容模式/i.test(line),
  )
  const osLine = important.find((line) => /^os:/i.test(line))
  const cnFirmwareLine = important.find((line) => /固件信息/.test(line))
  const cnBootLine = important.find((line) => /引导信息/.test(line))
  const bootromLine = important.find((line) => /bootrom/i.test(line))
  const firmwareLine = important.find((line) => /firmware|platform/i.test(line))
  const summary = osLine ?? cnFirmwareLine ?? cnBootLine ?? firmwareLine ?? bootromLine ?? important[0] ?? '已读取版本信息'

  return {
    summary: summary.slice(0, 96),
    details: important.slice(0, 4).map((line) => line.slice(0, 120)),
  }
}

function parseCardSnapshot(command: string, output: string): CardSnapshot | null {
  if (!/^(hf|lf)\b/.test(command)) {
    return null
  }

  const cleanLines = output
    .split(/\r?\n/)
    .map((line) => sanitizeOutputLine(line))
    .filter(Boolean)

  const interesting = cleanLines.filter((line) =>
    /uid|atqa|sak|type|tag|card|mifare|classic|ultralight|iso14443|em410|hid|t55|valid|found|blocks?/i.test(line),
  )

  if (!interesting.length) {
    return null
  }

  const joined = interesting.join('\n')
  const uidMatch = joined.match(/(?:uid|csn|card|id)[^0-9a-f]*([0-9a-f]{2}(?:[\s:-]?[0-9a-f]{2}){3,9})/i)
  const type = inferCardType(joined, command)
  const frequency = command.startsWith('hf') ? '13.56MHz 高频' : '125kHz 低频'
  const uid = uidMatch?.[1]?.replace(/[:-]/g, ' ').replace(/\s+/g, ' ').toUpperCase() ?? '未在输出中找到'

  return {
    title: type,
    uid,
    cardType: type,
    frequency,
    note: '这是从 PM3 输出里自动整理出来的摘要，完整内容仍保留在下方执行记录。',
    rows: interesting.slice(0, 8).map((line, index) => `${String(index).padStart(2, '0')}  ${line.slice(0, 72)}`),
  }
}

function inferCardType(text: string, command: string) {
  if (/mifare classic/i.test(text)) {
    return 'MIFARE Classic'
  }
  if (/ultralight|ntag/i.test(text)) {
    return 'MIFARE Ultralight / NTAG'
  }
  if (/iso14443-?a|14a/i.test(text)) {
    return 'ISO14443A'
  }
  if (/hid/i.test(text)) {
    return 'HID 低频卡'
  }
  if (/em410|em 410/i.test(text)) {
    return 'EM410x 低频卡'
  }
  if (/t55/i.test(text)) {
    return 'T55xx 低频卡'
  }
  return command.startsWith('hf') ? '高频卡' : '低频卡'
}

function sanitizeOutputLine(line: string) {
  return line
    .replace(ansiPattern, '')
    .replace(/^\[[=+!#-]\]\s*/, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function friendlyError(error: unknown) {
  if (error instanceof Error) {
    return error.message
  }

  return String(error)
}

function timeLabel() {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date())
}

export default App
