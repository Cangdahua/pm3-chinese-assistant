import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: root
    width: root.initialWindowWidth
    height: root.initialWindowHeight
    minimumWidth: root.minimumPhysicalWidth
    minimumHeight: root.minimumPhysicalHeight
    visible: false
    title: "PM3 中文助手"
    color: root.appBg

    SystemPalette {
        id: systemPalette
        colorGroup: SystemPalette.Active
    }

    Timer {
        id: terminalSuppressResetTimer
        interval: 1000
        repeat: false
        onTriggered: {
            if (backend.busy) {
                restart()
                return
            }
            root.terminalSuppressTyping = false
        }
    }

    property bool dangerUnlocked: false
    property string activePage: "13.56M卡"
    property string appearanceMode: "system"
    property string terminalRenderedLog: ""
    property bool terminalLogInitialized: false
    property bool terminalSuppressTyping: false
    property int terminalStopSerial: 0

    readonly property int headerHeight: 68
    readonly property int titlebarDragHeight: 0
    readonly property int trafficLightReserveWidth: 14
    readonly property int navHeight: 42
    readonly property int pageTop: headerHeight + navHeight
    readonly property int pageMargin: 16
    readonly property int sectionGap: 16

    readonly property int mainRowTop: 8
    readonly property int mainRow1Height: 360
    readonly property int mainRow2Height: 320
    readonly property int mainRow3Height: 356
    readonly property int mainRow1Y: mainRowTop
    readonly property int mainRow2Y: mainRow1Y + mainRow1Height + sectionGap
    readonly property int mainRow3Y: mainRow2Y + mainRow2Height + sectionGap

    readonly property int compactMinWidth: 980
    readonly property int compactMinHeight: 720
    readonly property int availableScreenWidth: Screen.desktopAvailableWidth > 0 ? Screen.desktopAvailableWidth : Screen.width
    readonly property int availableScreenHeight: Screen.desktopAvailableHeight > 0 ? Screen.desktopAvailableHeight : Screen.height

    readonly property int mainLogWidth: 640
    readonly property int mainCardWidth: 360
    readonly property int mainSectorWidth: 384
    readonly property int mainLogX: pageMargin
    readonly property int mainCardX: mainLogX + mainLogWidth + sectionGap
    readonly property int mainSectorX: mainCardX + mainCardWidth + sectionGap

    readonly property int mainSystemWidth: 300
    readonly property int mainReadWidth: 500
    readonly property int mainUidWidth: 288
    readonly property int mainKeysWidth: 284
    readonly property int mainSystemX: pageMargin
    readonly property int mainReadX: mainSystemX + mainSystemWidth + sectionGap
    readonly property int mainUidX: mainReadX + mainReadWidth + sectionGap
    readonly property int mainKeysX: mainUidX + mainUidWidth + sectionGap

    readonly property int mainWriteWidth: 650
    readonly property int mainExtraWidth: 746
    readonly property int mainWriteX: pageMargin
    readonly property int mainExtraX: mainWriteX + mainWriteWidth + sectionGap

    readonly property int mainDataWidth: 470
    readonly property int mainVendorWidth: 470
    readonly property int mainSafetyWidth: 444
    readonly property int mainDataX: pageMargin
    readonly property int mainVendorX: mainDataX + mainDataWidth + sectionGap
    readonly property int mainSafetyX: mainVendorX + mainVendorWidth + sectionGap

    readonly property int baseContentRightEdge: Math.max(
        mainSectorX + mainSectorWidth,
        mainKeysX + mainKeysWidth,
        mainExtraX + mainExtraWidth,
        mainSafetyX + mainSafetyWidth
    )
    readonly property int baseFullSectionWidth: baseContentRightEdge - pageMargin
    readonly property int fullSectionWidth: compactMode ? layoutWidth - 2 * pageMargin : Math.max(baseFullSectionWidth, root.width - 2 * pageMargin)
    readonly property int contentRightEdge: pageMargin + fullSectionWidth
    readonly property int mainRightX: 820
    readonly property int mainRightWidth: fullSectionWidth - (mainRightX - pageMargin)
    readonly property int mainRightHalfWidth: Math.floor((mainRightWidth - sectionGap) / 2)
    readonly property int standardTopY: 10
    readonly property int standardSecondY: 170
    readonly property int standardLogHeight: mainContentBottom - standardSecondY
    readonly property int twoColumnLeftWidth: compactMode ? Math.floor((fullSectionWidth - sectionGap) / 2) : 700
    readonly property int twoColumnRightX: pageMargin + twoColumnLeftWidth + sectionGap
    readonly property int twoColumnRightWidth: fullSectionWidth - twoColumnLeftWidth - sectionGap
    readonly property int icLeftWidth: compactMode ? Math.floor((fullSectionWidth - sectionGap) / 2) : 680
    readonly property int icRightX: pageMargin + icLeftWidth + sectionGap
    readonly property int icRightWidth: fullSectionWidth - icLeftWidth - sectionGap
    readonly property int mainContentBottom: mainRow3Y + mainRow3Height
    readonly property int standardContentBottom: standardSecondY + standardLogHeight
    readonly property int baseWindowWidth: baseContentRightEdge + pageMargin
    readonly property int baseWindowHeight: pageTop + Math.max(mainContentBottom, standardContentBottom) + pageMargin
    readonly property bool screenPrefersCompact: availableScreenWidth < baseWindowWidth + 48 || availableScreenHeight < baseWindowHeight + 48
    readonly property bool compactMode: screenPrefersCompact || root.width < baseWindowWidth || root.height < baseWindowHeight
    readonly property int layoutWidth: compactMode ? Math.max(compactMinWidth, root.width) : Math.max(baseWindowWidth, root.width)
    readonly property int layoutHeight: root.height
    readonly property int minimumPhysicalWidth: compactMinWidth
    readonly property int minimumPhysicalHeight: compactMinHeight
    readonly property int initialWindowWidth: screenPrefersCompact ? Math.max(compactMinWidth, Math.min(1180, availableScreenWidth - 48)) : baseWindowWidth
    readonly property int initialWindowHeight: screenPrefersCompact ? Math.max(compactMinHeight, Math.min(860, availableScreenHeight - 64)) : baseWindowHeight
    readonly property real uiScale: 1

    readonly property int compactCurrentY: mainRowTop
    readonly property int compactCurrentHeight: 300
    readonly property int compactDataY: compactCurrentY + compactCurrentHeight + sectionGap
    readonly property int compactDataHeight: 360
    readonly property int compactWorkflowY: compactDataY + compactDataHeight + sectionGap
    readonly property int compactWorkflowHeight: 320
    readonly property int compactGuideY: compactWorkflowY + compactWorkflowHeight + sectionGap
    readonly property int compactGuideHeight: 250
    readonly property int compactKeysY: compactGuideY + compactGuideHeight + sectionGap
    readonly property int compactKeysHeight: 356
    readonly property int compactMainContentBottom: compactKeysY + compactKeysHeight
    readonly property int pageViewportHeight: Math.max(0, root.height - root.pageTop)
    readonly property int advancedTerminalHeight: compactMode ? 360 : 430
    readonly property int advancedOperationsY: 10 + advancedTerminalHeight + sectionGap
    readonly property int advancedDeviceY: compactMode ? advancedOperationsY + 225 + sectionGap : advancedOperationsY
    readonly property int advancedCommandY: compactMode ? advancedDeviceY + 180 + sectionGap : advancedOperationsY + 225 + sectionGap
    readonly property int advancedContentBottom: advancedCommandY + 92
    readonly property int pageContentHeight: activePage === "高级"
        ? Math.max(advancedContentBottom + pageMargin, pageViewportHeight)
        : compactMode
            ? Math.max(compactMainContentBottom + pageMargin, pageViewportHeight)
            : Math.max(baseWindowHeight - pageTop, pageViewportHeight)

    readonly property bool systemDarkMode: (systemPalette.window.r + systemPalette.window.g + systemPalette.window.b) / 3 < 0.45
    readonly property bool darkMode: appearanceMode === "dark" || (appearanceMode === "system" && systemDarkMode)
    readonly property color appBg: darkMode ? "#101419" : "#f6f8fb"
    readonly property color pageBg: darkMode ? "#0f141a" : "#f5f7fb"
    readonly property color panelBg: darkMode ? "#171d24" : "#ffffff"
    readonly property color panelBorder: darkMode ? "#2c3642" : "#dde5ef"
    readonly property color dividerColor: darkMode ? "#252f3a" : "#edf1f6"
    readonly property color primaryText: darkMode ? "#eef4fb" : "#0f172a"
    readonly property color secondaryText: darkMode ? "#9aa8b8" : "#64748b"
    readonly property color buttonBg: darkMode ? "#1d2530" : "#f8fafc"
    readonly property color buttonPressedBg: darkMode ? "#243247" : "#dbeafe"
    readonly property color buttonBorder: darkMode ? "#344153" : "#cbd5e1"
    readonly property color dangerBg: darkMode ? "#321923" : "#fff1f2"
    readonly property color dangerBorder: darkMode ? "#7f2438" : "#fecdd3"
    readonly property color dangerText: darkMode ? "#ff8aa3" : "#be123c"
    readonly property color logBg: "#050807"
    readonly property color logTextColor: "#7cf7a7"
    readonly property color logBorderColor: "#163f2a"
    readonly property color logDimColor: "#3f7958"

    readonly property var pages: ["13.56M卡", "低频卡", "特殊卡", "高频模拟", "数据处理", "字典编辑", "软件设置", "高级"]

    readonly property var systemActions: [
        {label: "读取设备版本", command: "hw version", hint: "读取固件、FPGA 和兼容协议。"},
        {label: "天线电压", command: "hw tune", hint: "检测高频和低频天线。"},
        {label: "测试通信", command: "hw ping", hint: "确认 PM3 是否回应。"},
        {label: "设备状态", command: "hw status", hint: "查看内存、USB、FPGA 等状态。"}
    ]

    readonly property var icReadActions: [
        {label: "读取IC卡类型", command: "hf search", hint: "识别当前高频卡类型。"},
        {label: "默认密码扫描", command: "workflow mifare_default_key_scan", hint: "自动识别卡片容量，再扫描全部扇区的 A/B 密钥。"},
        {label: "本地撞库", command: "workflow mifare_classic_local_dict", hint: "用本机已收录字典按 UID 和默认库批量尝试密钥。"},
        {label: "继续破解缺失扇区", command: "workflow mifare_classic_nested_missing", hint: "自动找已知密钥，用 Nested 补齐缺失扇区。"},
        {label: "一键解析", command: "workflow mifare_classic_autopwn", hint: "按识别、扫密钥、读取整卡的内置流程执行。"},
        {label: "强力破解缺失扇区", command: "workflow mifare_classic_hardnested_missing", hint: "自动选择第一个缺失 Key 做 Hardnested。"}
    ]

    readonly property var uidActions: [
        {label: "读取UID卡", command: "hf 14a reader", hint: "读取 UID 和基础信息。"},
        {label: "修改UID", notice: "修改 UID 需要先明确新的 UID，并确认目标卡是可改 UID 的魔术卡。这个入口已移到「写卡向导」的 UID 工具里，后续会做成带输入框的确认向导。"},
        {label: "修复UID卡", notice: "修复 UID 需要先识别卡型、当前 UID 和目标卡类型。这里不会直接执行缺参数命令，避免误操作。"},
        {label: "锁定UFUID", notice: "锁定 UFUID 通常不可逆。后续会做成单独的危险操作确认向导。"}
    ]

    readonly property var extraActions: [
        {label: "辅助分析", command: "workflow mifare_nonce_assist", hint: "识别、弱随机数分析、采集随机数并刷新密钥。"},
        {label: "采集随机数", command: "workflow mifare_nonce_collect", hint: "采集 Mifare Classic 随机数到本地 nonces.bin。"},
        {label: "MFKeys恢复", command: "workflow mifare_mfkeys_recover", hint: "用默认密钥库恢复可用 Key，并同步密钥矩阵。"},
        {label: "高频记录", command: "hf list", hint: "查看最近的高频通信记录，辅助分析读卡过程。"}
    ]

    readonly property var lfActions: [
        {label: "低频寻卡", command: "lf search"},
        {label: "HID读取", command: "lf hid read"},
        {label: "EM410x读取", command: "lf em 410x_read"},
        {label: "Indala读取", command: "lf indala read"},
        {label: "T55xx检测", command: "lf t55xx detect"},
        {label: "T55xx配置", command: "lf t55xx config"},
        {label: "T55xx转储", command: "lf t55xx dump"},
        {label: "批量脚本", command: "script run lf_bulk_program", danger: true}
    ]

    readonly property var specialActions: [
        {label: "NTAG识别", command: "hf mfu info"},
        {label: "NTAG转储", command: "hf mfu dump", danger: true},
        {label: "NDEF解析", command: "script run ndef_dump"},
        {label: "Mifare Plus 只读识别", command: "workflow mifare_plus_inspect", hint: "仅执行安全搜索并显示 UID、SAK 和可能安全级别；SL3/AES 深度功能仍因固件能力未开放。"},
        {label: "iCLASS搜索", command: "hf iclass reader"},
        {label: "TNP3读取", command: "script run tnp3dump", danger: true},
        {label: "TNP3模拟", command: "script run tnp3sim", danger: true},
        {label: "TNP3克隆", command: "script run tnp3clone", danger: true}
    ]

    readonly property var emulateActions: [
        {label: "高频监听", command: "hf list"},
        {label: "14A原始命令", command: "script run 14araw", danger: true},
        {label: "Mifare模拟", command: "hf mf sim", danger: true},
        {label: "14A模拟", command: "hf 14a sim", danger: true},
        {label: "转储到模拟器", command: "script run dumptoemul", danger: true},
        {label: "模拟器导出", command: "script run emul2dump"},
        {label: "协议测试", command: "script run tracetest"},
        {label: "高级", page: "高级", hint: "打开命令行和低频维护入口。"}
    ]

    readonly property var dictionaryActions: [
        {label: "本地撞库", command: "workflow mifare_classic_local_dict"},
        {label: "默认密钥扫描", command: "workflow mifare_default_key_scan"},
        {label: "一卡一密分析", command: "workflow mifare_classic_nested_missing"},
        {label: "打开本地库", library: "openLocal"},
        {label: "保存当前密钥", library: "saveCurrent"},
        {label: "MFKeys恢复", command: "workflow mifare_mfkeys_recover"}
    ]

    function findPortIndex() {
        for (var i = 0; i < backend.ports.length; i++) {
            if (backend.ports[i] === backend.selectedPort)
                return i
        }
        return -1
    }

    function pageComponent(page) {
        if (page === "13.56M卡") return mainPage
        if (page === "低频卡") return lfPage
        if (page === "特殊卡") return specialPage
        if (page === "高频模拟") return emulatePage
        if (page === "数据处理") return dataPage
        if (page === "字典编辑") return dictionaryPage
        if (page === "软件设置") return settingsPage
        return advancedPage
    }

    function runAction(action) {
        if (action.notice) {
            backend.showNotice(action.label, action.notice)
            return
        }
        if (action.page) {
            root.activePage = action.page
            return
        }
        if (action.library === "openLocal") {
            backend.openKeyLibraryFolder()
            return
        }
        if (action.library === "saveCurrent") {
            backend.saveCurrentKeysToPersonalLibrary()
            return
        }
        guardedRun(action.label, action.command, Boolean(action.danger))
    }

    function guardedRun(label, command, danger) {
        if (danger && !root.dangerUnlocked) {
            backend.runPreset(label, command, true)
            return
        }
        backend.runAuthorizedCommand(label, command, root.dangerUnlocked)
    }

    Item {
        id: appCanvas
        width: root.layoutWidth
        height: root.layoutHeight
        scale: root.uiScale
        transformOrigin: Item.TopLeft

        Rectangle {
            anchors.fill: parent
            color: root.appBg
        }

        Rectangle {
            id: header
            x: 0
            y: 0
            width: root.layoutWidth
            height: root.headerHeight
            color: root.appBg
            border.color: "transparent"

            WindowDragZone {
                x: root.trafficLightReserveWidth
                y: 0
                width: parent.width - root.trafficLightReserveWidth
                height: root.titlebarDragHeight
                z: 3
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: root.trafficLightReserveWidth
                anchors.rightMargin: 18
                anchors.topMargin: root.titlebarDragHeight
                anchors.bottomMargin: 8
                spacing: 8
                z: 1

                ColumnLayout {
                    Layout.preferredWidth: root.compactMode ? 124 : 140
                    spacing: 2
                    Text {
                        text: "PM3 中文助手"
                        color: root.primaryText
                        font.pixelSize: root.compactMode ? 17 : 19
                        font.weight: Font.DemiBold
                    }
                    Text {
                        text: "本地离线工具 · v" + backend.appVersion
                        color: root.secondaryText
                        font.pixelSize: 11
                    }
                }

                AppComboBox {
                    id: portBox
                    Layout.preferredWidth: root.compactMode ? 170 : 200
                    Layout.preferredHeight: 30
                    model: backend.ports
                    currentIndex: root.findPortIndex()
                    onActivated: backend.selectedPort = currentText
                }

                HeaderButton {
                    text: "刷新设备"
                    Layout.preferredWidth: root.compactMode ? 62 : 70
                    onClicked: backend.refreshPorts()
                }

                HeaderButton {
                    text: "读取版本"
                    Layout.preferredWidth: root.compactMode ? 62 : 70
                    onClicked: backend.runCommand("读取设备版本", "hw version")
                }

                HeaderButton {
                    visible: !root.compactMode
                    text: "导入数据"
                    Layout.preferredWidth: 78
                    onClicked: backend.chooseDataFile()
                }

                StatusPill {
                    Layout.preferredWidth: root.compactMode ? 108 : 130
                    label: "状态"
                    value: backend.statusText
                    tone: backend.busy ? "amber" : backend.statusText === "失败" ? "rose" : "green"
                }

                StatusPill {
                    Layout.preferredWidth: root.compactMode ? 140 : 170
                    label: "设备"
                    value: backend.deviceText
                    tone: "blue"
                }

                StatusPill {
                    visible: !root.compactMode
                    Layout.preferredWidth: 120
                    label: "固件"
                    value: backend.firmwareText
                    tone: "neutral"
                }

                AppComboBox {
                    Layout.preferredWidth: root.compactMode ? 96 : 110
                    Layout.preferredHeight: 30
                    model: ["跟随系统", "白天", "黑夜"]
                    currentIndex: root.appearanceMode === "light" ? 1 : root.appearanceMode === "dark" ? 2 : 0
                    onActivated: function(index) {
                        root.appearanceMode = index === 1 ? "light" : index === 2 ? "dark" : "system"
                    }
                }

                Item { Layout.fillWidth: true }

                AppSwitch {
                    checked: root.dangerUnlocked
                    text: "允许危险操作"
                    onToggled: root.dangerUnlocked = checked
                }
            }
        }

        Rectangle {
            id: nav
            x: 0
            y: root.headerHeight
            width: root.layoutWidth
            height: root.navHeight
            color: root.appBg
            border.color: "transparent"

            Row {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 14
                anchors.topMargin: 4
                spacing: 6

                Repeater {
                    model: root.pages
                    delegate: NavItem {
                        width: (root.layoutWidth - 28 - 6 * (root.pages.length - 1)) / root.pages.length
                        height: 34
                        text: modelData
                        selected: root.activePage === modelData
                        onClicked: root.activePage = modelData
                    }
                }
            }
        }

        Rectangle {
            x: 0
            y: root.pageTop - 1
            width: root.layoutWidth
            height: 1
            color: root.panelBorder
        }

        Flickable {
            id: pageFlick
            x: 0
            y: root.pageTop
            width: root.layoutWidth
            height: root.pageViewportHeight
            contentWidth: root.layoutWidth
            contentHeight: root.pageContentHeight
            boundsBehavior: Flickable.StopAtBounds
            clip: true
            interactive: root.compactMode || contentHeight > height
            ScrollBar.vertical: ScrollBar {
                policy: pageFlick.contentHeight > pageFlick.height ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff
            }

            Loader {
                id: pageLoader
                width: root.layoutWidth
                height: root.pageContentHeight
                sourceComponent: root.pageComponent(root.activePage)
                onSourceComponentChanged: pageFlick.contentY = 0
            }
        }
    }

    Component {
        id: mainPage
        Item {
            width: root.layoutWidth
            height: root.pageContentHeight

            Section {
                x: root.pageMargin
                y: root.compactMode ? root.compactCurrentY : root.mainRow1Y
                width: root.compactMode ? root.fullSectionWidth : 590
                height: root.compactMode ? root.compactCurrentHeight : root.mainRow1Height
                title: "当前卡片"
                subtitle: "识别 / 记录"
                WorkbenchStatusPanel {}
            }

            Section {
                x: root.compactMode ? root.pageMargin : 618
                y: root.compactMode ? root.compactDataY : root.mainRow1Y
                width: root.compactMode ? root.fullSectionWidth : root.fullSectionWidth - 602
                height: root.compactMode ? root.compactDataHeight : root.mainRow1Height
                title: "数据区"
                subtitle: "左：读卡结果 / 右：待写入数据"
                CardDataTable {}
            }

            Section {
                x: root.pageMargin
                y: root.compactMode ? root.compactWorkflowY : root.mainRow2Y
                width: root.compactMode ? root.fullSectionWidth : 792
                height: root.compactMode ? root.compactWorkflowHeight : root.mainRow2Height
                title: "IC 破解流程"
                subtitle: "识别 → 扫密钥 → 解析 → 读整卡 → 校验 → 写卡"
                showStopButton: true
                CrackWorkflowPanel {}
            }

            Section {
                x: root.compactMode ? root.pageMargin : root.mainRightX
                y: root.compactMode ? root.compactGuideY : root.mainRow2Y
                width: root.compactMode ? Math.floor((root.fullSectionWidth - root.sectionGap) / 2) : root.mainRightHalfWidth
                height: root.compactMode ? root.compactGuideHeight : root.mainRow2Height
                title: "写卡向导"
                subtitle: "准备数据后再写入"
                WriteCardGuidePanel {}
            }

            Section {
                x: root.compactMode ? root.pageMargin + Math.floor((root.fullSectionWidth - root.sectionGap) / 2) + root.sectionGap : root.mainRightX + root.mainRightHalfWidth + root.sectionGap
                y: root.compactMode ? root.compactGuideY : root.mainRow2Y
                width: root.compactMode ? Math.ceil((root.fullSectionWidth - root.sectionGap) / 2) : root.mainRightHalfWidth
                height: root.compactMode ? root.compactGuideHeight : root.mainRow2Height
                title: "附加分析"
                subtitle: "随机数 / 记录 / 默认库"
                AnalysisGuidePanel {}
            }

            Section {
                x: root.pageMargin
                y: root.compactMode ? root.compactKeysY : root.mainRow3Y
                width: root.fullSectionWidth
                height: root.compactMode ? root.compactKeysHeight : root.mainRow3Height
                title: "密钥矩阵"
                subtitle: "扇区 / Key A / Key B / 状态"
                KeyMatrix {}
            }

        }
    }

    Component {
        id: icPage
        FixedGridPage {
            Section { x: root.pageMargin; y: root.standardTopY; width: root.icLeftWidth; height: root.compactMode ? 170 : 150; title: "13.56M 读取"; subtitle: "IC / Mifare"; ActionGrid { actions: root.icReadActions; gridColumns: 3 } }
            Section { x: root.icRightX; y: root.standardTopY; width: root.icRightWidth; height: root.compactMode ? 170 : 150; title: "写卡向导"; subtitle: "普通IC / 魔术卡 / UID"; WriteCardGuidePanel {} }
            Section { x: root.pageMargin; y: root.compactMode ? 196 : root.standardSecondY; width: root.compactMode ? root.icLeftWidth : root.mainDataWidth; height: 260; title: "扇区操作"; subtitle: "精确读写"; SectorPanel {} }
            Section { x: root.compactMode ? root.icRightX : 498; y: root.compactMode ? 196 : 170; width: root.compactMode ? root.icRightWidth : 450; height: 260; title: "UID操作"; subtitle: "UID / CUID / FUID"; ActionGrid { actions: root.uidActions; gridColumns: 2 } }
            Section { x: root.compactMode ? root.pageMargin : 960; y: root.compactMode ? 472 : 170; width: root.compactMode ? root.fullSectionWidth : 464; height: 260; title: "密钥状态"; subtitle: backend.dictionaryText; KeyMatrix {} }
            Section { x: root.pageMargin; y: root.compactMode ? 748 : 442; width: root.fullSectionWidth; height: root.compactMode ? root.pageContentHeight - 748 - root.pageMargin : root.mainContentBottom - 442; title: "执行记录"; subtitle: "中文输出"; ExecutionLog {} }
        }
    }

    Component {
        id: lfPage
        FixedGridPage {
            Section { x: root.pageMargin; y: root.standardTopY; width: root.twoColumnLeftWidth; height: 150; title: "低频读取"; subtitle: "125k / 134k"; ActionGrid { actions: root.lfActions; gridColumns: 4 } }
            Section { x: root.twoColumnRightX; y: root.standardTopY; width: root.twoColumnRightWidth; height: 150; title: "低频写入与测试"; subtitle: "T55xx / HID / EM"; ActionGrid { actions: [
                {label: "T55xx写入", command: "lf t55xx write", danger: true},
                {label: "HID模拟", command: "lf hid sim", danger: true},
                {label: "EM410x模拟", command: "lf em 410xsim", danger: true},
                {label: "ASK测试", command: "script run test_t55x7_ask", danger: true},
                {label: "FSK测试", command: "script run test_t55x7_fsk", danger: true},
                {label: "PSK测试", command: "script run test_t55x7_psk", danger: true},
                {label: "BI测试", command: "script run test_t55x7_bi", danger: true},
                {label: "批量脚本", command: "script run lf_bulk_program", danger: true}
            ]; gridColumns: 4 } }
            Section { x: root.pageMargin; y: root.standardSecondY; width: root.fullSectionWidth; height: root.standardLogHeight; title: "执行记录"; subtitle: "中文输出"; ExecutionLog {} }
        }
    }

    Component {
        id: specialPage
        FixedGridPage {
            Section { x: root.pageMargin; y: root.standardTopY; width: root.twoColumnLeftWidth; height: 150; title: "特殊卡"; subtitle: "NTAG / iCLASS / TNP3"; ActionGrid { actions: root.specialActions; gridColumns: 4 } }
            Section { x: root.twoColumnRightX; y: root.standardTopY; width: root.twoColumnRightWidth; height: 150; title: "特殊工具"; subtitle: "高级脚本"; ActionGrid { actions: [
                {label: "NDEF解析", command: "script run ndef_dump"},
                {label: "DI读取", command: "script run didump", danger: true},
                {label: "Remagic", command: "script run remagic", danger: true},
                {label: "参数工具", command: "script run parameters"},
                {label: "BruteSim", command: "script run brutesim", danger: true},
                {label: "高级", page: "高级", hint: "打开高级命令行。"}
            ]; gridColumns: 4 } }
            Section { x: root.pageMargin; y: root.standardSecondY; width: root.fullSectionWidth; height: root.standardLogHeight; title: "执行记录"; subtitle: "中文输出"; ExecutionLog {} }
        }
    }

    Component {
        id: emulatePage
        FixedGridPage {
            Section { x: root.pageMargin; y: root.standardTopY; width: root.twoColumnLeftWidth; height: 150; title: "高频模拟"; subtitle: "监听 / 模拟"; ActionGrid { actions: root.emulateActions; gridColumns: 4 } }
            Section { x: root.twoColumnRightX; y: root.standardTopY; width: root.twoColumnRightWidth; height: 150; title: "数据转换"; subtitle: "Dump / Emulator"; ActionGrid { actions: [
                {label: "Dump转模拟", command: "script run dumptoemul", danger: true},
                {label: "模拟转Dump", command: "script run emul2dump"},
                {label: "模拟HTML", command: "script run emul2html"},
                {label: "HTML报告", command: "script run htmldump"}
            ]; gridColumns: 4 } }
            Section { x: root.pageMargin; y: root.standardSecondY; width: root.fullSectionWidth; height: root.standardLogHeight; title: "执行记录"; subtitle: "中文输出"; ExecutionLog {} }
        }
    }

    Component {
        id: dataPage
        FixedGridPage {
            Section { x: root.pageMargin; y: root.standardTopY; width: root.fullSectionWidth; height: 360; title: "数据区"; subtitle: "左：读卡结果 / 右：待写入数据"; CardDataTable {} }
            Section { x: root.pageMargin; y: 382; width: root.fullSectionWidth; height: root.mainContentBottom - 382; title: "执行记录"; subtitle: "中文输出"; ExecutionLog {} }
        }
    }

    Component {
        id: dictionaryPage
        FixedGridPage {
            Section { x: root.pageMargin; y: root.standardTopY; width: root.twoColumnLeftWidth; height: 170; title: "字典库"; subtitle: backend.dictionaryText; ActionGrid { actions: root.dictionaryActions; gridColumns: 3 } }
            Section { x: root.twoColumnRightX; y: root.standardTopY; width: root.twoColumnRightWidth; height: 170; title: "我的密钥库"; subtitle: backend.keyLibraryText; MyKeyLibraryPanel {} }
            Section { x: root.pageMargin; y: 190; width: root.fullSectionWidth; height: root.mainContentBottom - 190; title: "执行记录"; subtitle: "中文输出"; ExecutionLog {} }
        }
    }

    Component {
        id: settingsPage
        FixedGridPage {
            Section { x: root.pageMargin; y: root.standardTopY; width: root.twoColumnLeftWidth; height: 205; title: "当前设备"; subtitle: "连接状态"; DeviceInfoPanel {} }
            Section { x: root.twoColumnRightX; y: root.standardTopY; width: root.twoColumnRightWidth; height: 205; title: "安全开关"; subtitle: "写卡保护"; SafetyPanel {} }
            Section { x: root.pageMargin; y: 230; width: root.fullSectionWidth; height: root.mainContentBottom - 230; title: "执行记录"; subtitle: "中文输出"; ExecutionLog {} }
        }
    }

    Component {
        id: advancedPage
        FixedGridPage {
            Section { x: root.pageMargin; y: 10; width: root.fullSectionWidth; height: root.advancedTerminalHeight; title: "执行记录"; subtitle: "中文输出"; ExecutionLog {} }
            Section { x: root.compactMode ? root.pageMargin : root.mainDataX; y: root.advancedOperationsY; width: root.compactMode ? root.icLeftWidth : root.mainDataWidth; height: 225; title: "魔术卡维护"; subtitle: "拆步修复 / UID / 初始化"; MagicMaintenancePanel {} }
            Section { x: root.compactMode ? root.icRightX : root.mainVendorX; y: root.advancedOperationsY; width: root.compactMode ? root.icRightWidth : root.mainVendorWidth; height: 225; title: "扇区高精操作"; subtitle: "知道扇区和密钥时使用"; SectorMiniPanel {} }
            Section { x: root.compactMode ? root.pageMargin : root.mainSafetyX; y: root.advancedDeviceY; width: root.compactMode ? root.fullSectionWidth : root.mainSafetyWidth; height: root.compactMode ? 180 : 225; title: "设备维护"; subtitle: "通信 / 日志 / 工作区"; AdvancedDevicePanel {} }
            Section { x: root.pageMargin; y: root.advancedCommandY; width: root.fullSectionWidth; height: 92; title: "命令行"; subtitle: "直接执行 PM3 命令"; CommandPanel {} }
        }
    }

    component FixedGridPage: Item {
        default property alias content: pageContent.data
        width: root.layoutWidth
        height: root.pageContentHeight
        Rectangle {
            anchors.fill: parent
            color: root.pageBg
        }
        Item {
            id: pageContent
            anchors.fill: parent
        }
    }

    component Section: Rectangle {
        id: sectionRoot
        property string title: ""
        property string subtitle: ""
        property bool showStopButton: false
        default property alias content: body.data
        radius: 10
        color: root.panelBg
        border.color: root.panelBorder
        clip: true

        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: "transparent"
            border.color: "transparent"
        }

        Text {
            id: sectionTitle
            x: 14
            y: 8
            text: title
            color: root.primaryText
            font.pixelSize: 14
            font.weight: Font.DemiBold
        }

        Text {
            x: 14
            y: 26
            width: parent.width - 28 - (sectionRoot.showStopButton ? 82 : 0)
            text: subtitle
            color: root.secondaryText
            font.pixelSize: 11
            elide: Text.ElideRight
        }

        Rectangle {
            id: sectionStopButton
            visible: sectionRoot.showStopButton
            x: parent.width - width - 14
            y: 8
            width: 62
            height: 26
            radius: 7
            z: 4
            color: stopMouse.pressed ? root.buttonPressedBg : root.dangerBg
            border.color: root.dangerBorder
            opacity: backend.busy ? 1 : 0.85
            Text {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                text: "终止"
                color: root.dangerText
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.pixelSize: 12
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }
            MouseArea {
                id: stopMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    root.terminalSuppressTyping = true
                    root.terminalStopSerial += 1
                    terminalSuppressResetTimer.restart()
                    backend.stopCurrentCommand()
                }
            }
            ToolTip.visible: stopMouse.containsMouse
            ToolTip.delay: 450
            ToolTip.text: backend.busy ? "终止当前正在执行的操作" : "当前没有正在执行的操作"
        }

        Rectangle {
            x: 0
            y: 40
            width: parent.width
            height: 1
            color: root.dividerColor
        }

        Item {
            id: body
            x: 0
            y: 41
            width: parent.width
            height: parent.height - 41
        }
    }

    component ActionGrid: GridLayout {
        property var actions: []
        property int gridColumns: 4
        anchors.fill: parent
        anchors.margins: 10
        columns: gridColumns
        rowSpacing: 8
        columnSpacing: 8

        Repeater {
            model: actions
            delegate: SmallButton {
                Layout.fillWidth: true
                text: modelData.label
                danger: Boolean(modelData.danger)
                hint: String(modelData.hint || "")
                onClicked: root.runAction(modelData)
            }
        }
    }

    component SmallButton: Rectangle {
        id: control
        property string text: ""
        property bool danger: false
        property string hint: ""
        signal clicked()
        implicitWidth: 84
        implicitHeight: 30
        Layout.fillWidth: true
        Layout.preferredHeight: 30
        radius: 7
        color: mouseArea.pressed ? root.buttonPressedBg : control.danger ? root.dangerBg : root.buttonBg
        border.color: control.danger ? root.dangerBorder : root.buttonBorder
        opacity: backend.busy ? 0.56 : 1
        ToolTip.visible: mouseArea.containsMouse && hint.length > 0
        ToolTip.delay: 500
        ToolTip.text: hint

        Text {
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            text: control.text
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            color: control.danger ? root.dangerText : root.primaryText
            font.pixelSize: 12
            font.weight: Font.DemiBold
            elide: Text.ElideRight
        }

        MouseArea {
            id: mouseArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: backend.busy ? Qt.ArrowCursor : Qt.PointingHandCursor
            onClicked: {
                if (!backend.busy)
                    control.clicked()
            }
        }
    }

    component ExportDataButton: Rectangle {
        id: control
        property var formats: ["BIN", "DUMP", "MFD", "EML", "JSON", "TXT"]
        implicitWidth: 118
        implicitHeight: 30
        Layout.minimumWidth: 108
        Layout.preferredWidth: 118
        Layout.fillWidth: false
        Layout.preferredHeight: 30
        radius: 7
        color: mouseArea.pressed ? root.buttonPressedBg : root.buttonBg
        border.color: root.buttonBorder
        opacity: backend.busy ? 0.56 : 1

        Text {
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            text: "导出数据  v"
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            color: root.primaryText
            font.pixelSize: 12
            font.weight: Font.DemiBold
            elide: Text.ElideRight
        }

        MouseArea {
            id: mouseArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: backend.busy ? Qt.ArrowCursor : Qt.PointingHandCursor
            onClicked: {
                if (!backend.busy)
                    exportPopup.open()
            }
        }

        Popup {
            id: exportPopup
            x: 0
            y: control.height + 4
            width: control.width
            padding: 4
            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent
            background: Rectangle {
                radius: 8
                color: root.panelBg
                border.color: root.panelBorder
            }
            contentItem: ColumnLayout {
                spacing: 3
                Repeater {
                    model: control.formats
                    delegate: Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 28
                        radius: 6
                        color: optionMouse.containsMouse ? root.buttonPressedBg : "transparent"
                        Text {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            text: modelData
                            color: root.primaryText
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                            verticalAlignment: Text.AlignVCenter
                            horizontalAlignment: Text.AlignHCenter
                        }
                        MouseArea {
                            id: optionMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                exportPopup.close()
                                backend.exportCardReadData(modelData)
                            }
                        }
                    }
                }
            }
        }
    }

    component WindowDragZone: MouseArea {
        property real startX: 0
        property real startY: 0
        cursorShape: Qt.ArrowCursor
        acceptedButtons: Qt.LeftButton
        onPressed: function(mouse) {
            startX = mouse.x
            startY = mouse.y
            if (root.startSystemMove())
                return
        }
        onPositionChanged: function(mouse) {
            if (!pressed)
                return
            root.x += mouse.x - startX
            root.y += mouse.y - startY
        }
    }

    component HeaderButton: Rectangle {
        id: control
        property string text: ""
        property bool danger: false
        property bool enabledWhenBusy: false
        signal clicked()
        Layout.preferredHeight: 30
        radius: 7
        color: mouseArea.pressed ? root.buttonPressedBg : control.danger ? root.dangerBg : root.buttonBg
        border.color: control.danger ? root.dangerBorder : root.buttonBorder
        opacity: backend.busy && !control.enabledWhenBusy ? 0.58 : 1

        Text {
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            text: control.text
            color: control.danger ? root.dangerText : root.primaryText
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            font.pixelSize: 12
            font.weight: Font.DemiBold
            elide: Text.ElideRight
        }

        MouseArea {
            id: mouseArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: backend.busy && !control.enabledWhenBusy ? Qt.ArrowCursor : Qt.PointingHandCursor
            onClicked: {
                if (!backend.busy || control.enabledWhenBusy)
                    control.clicked()
            }
        }
    }

    component AppTextField: TextField {
        id: control
        color: root.primaryText
        placeholderTextColor: root.secondaryText
        selectedTextColor: root.darkMode ? "#07111f" : "#0f172a"
        selectionColor: root.darkMode ? "#7cb2ff" : "#93c5fd"
        font.pixelSize: 12
        leftPadding: 8
        rightPadding: 8
        verticalAlignment: TextInput.AlignVCenter
        background: Rectangle {
            radius: 5
            color: root.darkMode ? "#121821" : "#ffffff"
            border.color: control.activeFocus ? "#60a5fa" : root.panelBorder
        }
    }

    component AppComboBox: ComboBox {
        id: control
        font.pixelSize: 12
        contentItem: Text {
            leftPadding: 9
            rightPadding: 22
            text: control.displayText
            color: root.primaryText
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            font.pixelSize: 12
        }
        indicator: Text {
            x: control.width - width - 8
            y: (control.height - height) / 2
            text: "v"
            color: root.secondaryText
            font.pixelSize: 10
            font.weight: Font.DemiBold
        }
        background: Rectangle {
            radius: 7
            color: root.buttonBg
            border.color: control.activeFocus ? "#60a5fa" : root.buttonBorder
        }
        delegate: ItemDelegate {
            width: control.width
            height: 28
            highlighted: control.highlightedIndex === index
            contentItem: Text {
                text: modelData
                color: root.primaryText
                font.pixelSize: 12
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
            }
            background: Rectangle {
                color: highlighted ? root.buttonPressedBg : root.panelBg
            }
        }
        popup: Popup {
            y: control.height + 3
            width: control.width
            implicitHeight: Math.min(220, control.count * 28 + 2)
            padding: 1
            contentItem: ListView {
                clip: true
                implicitHeight: contentHeight
                model: control.popup.visible ? control.delegateModel : null
                currentIndex: control.highlightedIndex
            }
            background: Rectangle {
                radius: 7
                color: root.panelBg
                border.color: root.panelBorder
            }
        }
    }

    component AppSwitch: Switch {
        id: control
        spacing: 8
        indicator: Rectangle {
            implicitWidth: 38
            implicitHeight: 22
            x: control.leftPadding
            y: parent.height / 2 - height / 2
            radius: height / 2
            color: control.checked ? (root.darkMode ? "#0f6b45" : "#dcfce7") : (root.darkMode ? "#2a3340" : "#e5e7eb")
            border.color: control.checked ? (root.darkMode ? "#34d399" : "#86efac") : root.buttonBorder
            Rectangle {
                width: 16
                height: 16
                radius: 8
                x: control.checked ? parent.width - width - 3 : 3
                y: 3
                color: control.checked ? (root.darkMode ? "#d1fae5" : "#16a34a") : (root.darkMode ? "#cbd5e1" : "#ffffff")
                Behavior on x { NumberAnimation { duration: 120 } }
            }
        }
        contentItem: Text {
            text: control.text
            color: root.primaryText
            font.pixelSize: 12
            verticalAlignment: Text.AlignVCenter
            leftPadding: control.indicator.width + control.spacing
        }
    }

    component NavItem: Rectangle {
        id: item
        property string text: ""
        property bool selected: false
        signal clicked()
        radius: 8
        color: selected ? (root.darkMode ? "#14233a" : "#eaf2ff") : "transparent"
        border.color: selected ? (root.darkMode ? "#2d5f9f" : "#bfdbfe") : "transparent"

        Text {
            anchors.fill: parent
            text: item.text
            color: item.selected ? (root.darkMode ? "#8fbaff" : "#1d4ed8") : root.secondaryText
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            font.pixelSize: 13
            font.weight: item.selected ? Font.DemiBold : Font.Normal
            elide: Text.ElideRight
        }

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: item.clicked()
        }
    }

    component StatusPill: Rectangle {
        property string label: ""
        property string value: ""
        property string tone: "blue"
        height: 30
        radius: 8
        color: tone === "green" ? (root.darkMode ? "#10281d" : "#ecfdf5") : tone === "amber" ? (root.darkMode ? "#2b2112" : "#fff7ed") : tone === "rose" ? (root.darkMode ? "#301822" : "#fff1f2") : tone === "neutral" ? (root.darkMode ? "#1a212b" : "#f8fafc") : (root.darkMode ? "#13233a" : "#eff6ff")
        border.color: tone === "green" ? (root.darkMode ? "#2d6b4d" : "#bbf7d0") : tone === "amber" ? (root.darkMode ? "#7c5525" : "#fed7aa") : tone === "rose" ? (root.darkMode ? "#7f2438" : "#fecdd3") : tone === "neutral" ? root.panelBorder : (root.darkMode ? "#315f9b" : "#bfdbfe")
        RowLayout {
            anchors.fill: parent
            anchors.margins: 7
            spacing: 7
            Text {
                text: label
                color: tone === "green" ? (root.darkMode ? "#7dd7a8" : "#166534") : tone === "amber" ? (root.darkMode ? "#f0b46b" : "#9a3412") : tone === "rose" ? root.dangerText : tone === "neutral" ? root.secondaryText : (root.darkMode ? "#8fbaff" : "#1d4ed8")
                font.pixelSize: 12
                font.weight: Font.DemiBold
            }
            Text {
                text: value
                color: root.primaryText
                font.pixelSize: 12
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }
    }

    component ExecutionLog: Rectangle {
        id: terminal
        property string displayedText: ""
        property string pendingText: ""
        anchors.fill: parent
        anchors.margins: 12
        color: root.logBg
        radius: 8
        border.color: root.logBorderColor
        border.width: 1
        clip: true

        function shouldRenderInstant(text) {
            if (text.length > 900)
                return true
            var lines = text.split("\n")
            if (lines.length > 18)
                return true
            var tableRows = 0
            var denseRows = 0
            for (var i = 0; i < lines.length; i++) {
                var line = lines[i]
                if (line.indexOf("|---|") >= 0 || line.match(/^[|][0-9]{2,3}[|]/))
                    tableRows++
                if (line.match(/[0-9A-Fa-f]{12}/) && (line.indexOf("|") >= 0 || line.length > 48))
                    denseRows++
            }
            if (tableRows >= 4 || denseRows >= 6)
                return true
            if (text.indexOf("dumpdata.bin") >= 0 && lines.length > 12)
                return true
            return false
        }

        function beginTyping(newText) {
            if (root.terminalSuppressTyping) {
                typeTimer.stop()
                pendingText = ""
                displayedText = newText
                root.terminalRenderedLog = newText
                Qt.callLater(logFlick.scrollToBottom)
                return
            }
            if (newText.indexOf(displayedText) === 0) {
                pendingText = newText.slice(displayedText.length)
            } else {
                displayedText = ""
                root.terminalRenderedLog = ""
                pendingText = newText
            }
            if (shouldRenderInstant(pendingText)) {
                typeTimer.stop()
                pendingText = ""
                displayedText = newText
                root.terminalRenderedLog = newText
                Qt.callLater(logFlick.scrollToBottom)
                return
            }
            typeTimer.restart()
        }

        function stopTypingNow() {
            typeTimer.stop()
            pendingText = ""
            displayedText = backend.logText
            root.terminalRenderedLog = backend.logText
            Qt.callLater(logFlick.scrollToBottom)
        }

        Component.onCompleted: {
            if (root.terminalLogInitialized) {
                displayedText = root.terminalRenderedLog || backend.logText
                pendingText = ""
                if (backend.logText.indexOf(displayedText) !== 0) {
                    displayedText = backend.logText
                    root.terminalRenderedLog = backend.logText
                }
                if (backend.logText.indexOf(displayedText) === 0 && backend.logText.length > displayedText.length)
                    beginTyping(backend.logText)
                Qt.callLater(logFlick.scrollToBottom)
            } else {
                root.terminalLogInitialized = true
                beginTyping(backend.logText)
            }
        }

        Timer {
            id: typeTimer
            interval: 9
            repeat: true
            onTriggered: {
                if (terminal.pendingText.length <= 0) {
                    stop()
                    return
                }
                var amount = terminal.pendingText.length > 1200 ? 32 : terminal.pendingText.length > 420 ? 14 : terminal.pendingText.length > 140 ? 7 : 3
                terminal.displayedText += terminal.pendingText.slice(0, amount)
                terminal.pendingText = terminal.pendingText.slice(amount)
                root.terminalRenderedLog = terminal.displayedText
                Qt.callLater(logFlick.scrollToBottom)
            }
        }

        Flickable {
            id: logFlick
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: progressDock.visible ? progressDock.top : parent.bottom
            anchors.leftMargin: 12
            anchors.rightMargin: 10
            anchors.topMargin: 10
            anchors.bottomMargin: progressDock.visible ? 6 : 10
            contentWidth: width
            contentHeight: logText.implicitHeight
            boundsBehavior: Flickable.StopAtBounds
            clip: true

            function scrollToBottom() {
                contentY = Math.max(0, contentHeight - height)
            }

            Connections {
                target: backend
                function onLogTextChanged() {
                    terminal.beginTyping(backend.logText)
                    Qt.callLater(logFlick.scrollToBottom)
                }
            }

            Connections {
                target: root
                function onTerminalStopSerialChanged() {
                    terminal.stopTypingNow()
                }
            }

            TextEdit {
                id: logText
                width: logFlick.width
                text: terminal.displayedText + (typeTimer.running ? " █" : "")
                readOnly: true
                selectByMouse: true
                textFormat: TextEdit.PlainText
                wrapMode: TextEdit.Wrap
                font.family: "Menlo"
                font.pixelSize: 12
                color: root.logTextColor
                selectedTextColor: "#061008"
                selectionColor: "#8fffb7"
                onImplicitHeightChanged: Qt.callLater(logFlick.scrollToBottom)
            }

            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
                contentItem: Rectangle {
                    implicitWidth: 5
                    radius: 3
                    color: root.logDimColor
                    opacity: 0.7
                }
                background: Rectangle {
                    color: "transparent"
                }
            }
        }

        Rectangle {
            id: progressDock
            visible: backend.busy && backend.progressText.length > 0
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.leftMargin: 10
            anchors.rightMargin: 10
            anchors.bottomMargin: 8
            height: 26
            radius: 7
            color: "#07130c"
            border.color: "#1f6f3d"
            clip: true
            Text {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                text: backend.progressText
                color: "#8fffb7"
                font.family: "Menlo"
                font.pixelSize: 12
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
            }
        }
    }

    component WorkbenchStatusPanel: ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 6
        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            FlowStepChip { label: "识别"; value: backend.deviceText }
            FlowStepChip { label: "固件"; value: backend.firmwareText }
            FlowStepChip { label: "数据"; value: backend.dataWorkspaceText }
        }
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: root.logBg
            radius: 8
            clip: true
            ExecutionLog {
                anchors.fill: parent
                anchors.margins: 0
            }
        }
    }

    component CrackWorkflowPanel: GridLayout {
        anchors.fill: parent
        anchors.margins: 10
        columns: 3
        rowSpacing: 10
        columnSpacing: 10

        WorkflowStepCard {
            step: "1"
            title: "识别卡片"
            detail: "先确认是不是 Mifare Classic。只有卡型对了，后面的扫密钥才有意义。"
            buttonText: "开始识别"
            command: "hf search"
        }
        WorkflowStepCard {
            step: "2"
            title: "扫密钥"
            detail: "先扫常见默认密钥；如果不够，再用本地撞库按 UID 和随包字典继续试。"
            buttonText: "扫描密钥"
            command: "hf mf chk *1 ? d"
            secondaryButtonText: "本地撞库"
            secondaryCommand: "workflow mifare_classic_local_dict"
        }
        WorkflowStepCard {
            step: "3"
            title: "继续解析"
            detail: "默认密钥不够时，自动找已知密钥，用 Nested 继续补齐缺失扇区。"
            buttonText: "继续破解"
            command: "workflow mifare_classic_nested_missing"
            secondaryButtonText: "强力破解"
            secondaryCommand: "workflow mifare_classic_hardnested_missing"
        }
        WorkflowStepCard {
            step: "4"
            title: "读取整卡"
            detail: "密钥尽量补齐后读取整卡数据，生成可备份的 dumpdata.bin。"
            buttonText: "读取整卡"
            command: "hf mf dump"
        }
        WorkflowStepCard {
            step: "5"
            title: "校验数据"
            detail: "检查工作区里有没有卡片数据、密钥文件，以及是否具备写卡条件。"
            buttonText: "校验工作区"
            mode: "verify"
        }
        WorkflowStepCard {
            step: "6"
            title: "确认后写卡"
            detail: "确认目标卡类型匹配后，再打开允许危险操作。该开关默认会一直锁住。"
            buttonText: "写入卡片"
            mode: "write"
            danger: true
        }
    }

    component WorkflowStepCard: Rectangle {
        id: card
        property string step: ""
        property string title: ""
        property string detail: ""
        property string buttonText: ""
        property string command: ""
        property string secondaryButtonText: ""
        property string secondaryCommand: ""
        property string mode: "command"
        property bool danger: false
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.preferredHeight: 124
        radius: 9
        color: root.darkMode ? "#121a24" : "#f8fafc"
        border.color: danger ? root.dangerBorder : root.panelBorder

        function runStep() {
            if (mode === "verify") {
                backend.verifyWorkspaceData()
                return
            }
            if (mode === "write") {
                backend.writeSelectedDataToCard(root.dangerUnlocked)
                return
            }
            if (danger) {
                root.guardedRun(title, command, true)
                return
            }
            backend.runCommand(title, command)
        }

        function runSecondaryStep() {
            backend.runCommand(secondaryButtonText, secondaryCommand)
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 9
            spacing: 6
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Rectangle {
                    Layout.preferredWidth: 24
                    Layout.preferredHeight: 24
                    radius: 12
                    color: card.danger ? root.dangerBg : (root.darkMode ? "#173050" : "#eaf2ff")
                    border.color: card.danger ? root.dangerBorder : (root.darkMode ? "#3d6ea8" : "#93c5fd")
                    Text {
                        anchors.centerIn: parent
                        text: card.step
                        color: card.danger ? root.dangerText : (root.darkMode ? "#9fcbff" : "#1d4ed8")
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                    }
                }
                Text {
                    Layout.fillWidth: true
                    text: card.title
                    color: root.primaryText
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
            }
            Text {
                Layout.fillWidth: true
                Layout.fillHeight: true
                text: card.detail
                color: root.secondaryText
                font.pixelSize: 11
                wrapMode: Text.WordWrap
                lineHeight: 1.08
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                SmallButton {
                    Layout.fillWidth: true
                    text: card.buttonText
                    danger: card.danger
                    onClicked: card.runStep()
                }
                SmallButton {
                    Layout.fillWidth: true
                    visible: card.secondaryButtonText.length > 0
                    text: card.secondaryButtonText
                    onClicked: card.runSecondaryStep()
                }
            }
        }
    }

    component AnalysisGuidePanel: ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 78
            radius: 8
            color: root.darkMode ? "#101822" : "#f8fafc"
            border.color: root.panelBorder
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 4
                Text {
                    Layout.fillWidth: true
                    text: "适合密钥还没补齐的时候用"
                    color: root.primaryText
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
                Text {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    text: "先分析弱随机数，再采集 nonces.bin，并把能恢复的密钥同步到密钥矩阵。全程只读，不写卡。"
                    color: root.secondaryText
                    font.pixelSize: 11
                    wrapMode: Text.WordWrap
                    lineHeight: 1.08
                }
            }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 2
            rowSpacing: 8
            columnSpacing: 8
            SmallButton {
                Layout.columnSpan: 2
                Layout.fillWidth: true
                text: "一键辅助分析"
                hint: "自动执行识别、弱随机数分析、采集随机数、查看高频记录和默认库恢复。"
                onClicked: backend.runCommand("辅助分析", "workflow mifare_nonce_assist")
            }
            SmallButton {
                text: "采集随机数"
                hint: "生成 nonces.bin，给后续 Hardnested 或高级分析使用。"
                onClicked: backend.runCommand("采集随机数", "workflow mifare_nonce_collect")
            }
            SmallButton {
                text: "MFKeys恢复"
                hint: "用默认密钥库恢复可用密钥，并刷新密钥矩阵。"
                onClicked: backend.runCommand("MFKeys恢复", "workflow mifare_mfkeys_recover")
            }
            SmallButton {
                text: "高频记录"
                hint: "查看 PM3 最近记录到的高频通信内容。"
                onClicked: backend.runCommand("高频记录", "hf list")
            }
            SmallButton {
                text: "载入密钥"
                hint: "从本地 dumpkeys.bin 重新载入到密钥矩阵。"
                onClicked: backend.loadWorkspaceKeys()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 8
            color: root.darkMode ? "#0f171f" : "#fbfdff"
            border.color: root.dividerColor
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 9
                spacing: 3
                CompactInfoLine { text: "结果位置：密钥矩阵 / dumpkeys.bin / nonces.bin" }
                CompactInfoLine { text: "适用对象：Mifare Classic、S50、S70" }
                CompactInfoLine { text: "如果还缺密钥：继续用 Nested 或 Hardnested" }
            }
        }
    }

    component FlowStepChip: Rectangle {
        property string label: ""
        property string value: ""
        Layout.fillWidth: true
        Layout.preferredHeight: 38
        radius: 7
        color: root.darkMode ? "#121a24" : "#f8fafc"
        border.color: root.panelBorder
        ColumnLayout {
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            anchors.topMargin: 4
            anchors.bottomMargin: 4
            spacing: 0
            Text {
                text: label
                color: root.secondaryText
                font.pixelSize: 10
                font.weight: Font.DemiBold
            }
            Text {
                Layout.fillWidth: true
                text: value
                color: root.primaryText
                font.pixelSize: 11
                elide: Text.ElideRight
            }
        }
    }

    component CardDataTable: ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 8
            CardDataPane {
                Layout.fillWidth: true
                Layout.fillHeight: true
                title: "读卡数据"
                subtitle: "从当前卡片读取"
                infoText: backend.cardReadDataText
                planText: "只读预览，不会直接写卡"
                blocks: backend.cardReadBlocks
                selectedIndex: backend.selectedCardReadBlockIndex
                selectedLabel: backend.selectedCardReadBlockLabel
                selectedValue: backend.selectedCardReadBlockValue
                selectedIsTrailer: backend.selectedCardReadBlockIsTrailer
                readPane: true
            }
            Rectangle {
                Layout.preferredWidth: 1
                Layout.fillHeight: true
                color: root.dividerColor
            }
            CardDataPane {
                Layout.fillWidth: true
                Layout.fillHeight: true
                title: "待写入数据"
                subtitle: "导入或从左侧复制"
                infoText: backend.dataWorkspaceText
                planText: backend.writePlanText
                capabilityText: backend.cardCapabilityText
                transactionText: backend.writeTransactionText
                blocks: backend.dataBlocks
                selectedIndex: backend.selectedDataBlockIndex
                selectedLabel: backend.selectedDataBlockLabel
                selectedValue: backend.selectedDataBlockValue
                selectedIsTrailer: backend.selectedDataBlockIsTrailer
                readPane: false
            }
        }
    }

    component CardDataPane: ColumnLayout {
        id: pane
        property string title: ""
        property string subtitle: ""
        property string infoText: ""
        property string planText: ""
        property string capabilityText: ""
        property string transactionText: ""
        property var blocks: []
        property int selectedIndex: 0
        property string selectedLabel: "--"
        property string selectedValue: "--"
        property bool selectedIsTrailer: false
        property bool readPane: false
        spacing: 5
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0
                Text {
                    Layout.fillWidth: true
                    text: pane.title
                    color: root.primaryText
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
                Text {
                    Layout.fillWidth: true
                    text: pane.subtitle
                    color: root.secondaryText
                    font.pixelSize: 10
                    elide: Text.ElideRight
                }
            }
            SmallButton {
                Layout.preferredWidth: 56
                text: "清空"
                hint: pane.readPane ? "清空左侧读卡显示，不会删除你的导出文件。" : "清空右侧待写入数据和写卡计划。"
                onClicked: {
                    if (pane.readPane)
                        backend.clearCardReadData()
                    else
                        backend.clearPendingWriteData()
                }
            }
        }
        CompactInfoLine { Layout.fillWidth: true; text: pane.infoText }
        CompactInfoLine { Layout.fillWidth: true; text: pane.planText }
        CompactInfoLine {
            Layout.fillWidth: true
            visible: !pane.readPane && (pane.capabilityText.length > 0 || pane.transactionText.length > 0)
            text: pane.capabilityText + (pane.capabilityText.length > 0 && pane.transactionText.length > 0 ? "　" : "") + pane.transactionText
        }
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 24
            radius: 6
            color: root.darkMode ? "#111923" : "#f1f5f9"
            border.color: root.buttonBorder
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 8
                TableHeaderText { text: "区/块"; Layout.preferredWidth: 48 }
                TableHeaderText { text: "16字节数据（共 " + pane.blocks.length + " 块）"; Layout.fillWidth: true }
                TableHeaderText { text: "类型"; Layout.preferredWidth: 58 }
            }
        }
        Flickable {
            id: cardDataFlick
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: width
            contentHeight: tableRows.implicitHeight
            boundsBehavior: Flickable.StopAtBounds
            Component.onCompleted: resetDataScrollTimer.start()
            Timer {
                id: resetDataScrollTimer
                interval: 120
                repeat: false
                onTriggered: cardDataFlick.contentY = 0
            }
            Connections {
                target: backend
                function onDataBlocksChanged() {
                    resetDataScrollTimer.restart()
                }
                function onCardReadBlocksChanged() {
                    resetDataScrollTimer.restart()
                }
            }
            ColumnLayout {
                id: tableRows
                width: parent.width
                spacing: 4
                Repeater {
                    model: pane.blocks
                    delegate: DataTableRow {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 28
                        blockIndex: index
                        label: modelData.label
                        value: modelData.value
                        manufacturer: index === 0
                        trailer: Boolean(modelData.trailer)
                        selected: pane.selectedIndex === index
                        onPicked: function(blockIndex) {
                            if (pane.readPane)
                                backend.selectCardReadBlock(blockIndex)
                            else
                                backend.selectDataBlock(blockIndex)
                        }
                    }
                }
            }
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AlwaysOn }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            StatusPill {
                Layout.preferredWidth: 92
                label: "当前"
                value: pane.selectedLabel
                tone: pane.selectedIndex === 0 ? "blue" : pane.selectedIsTrailer ? "amber" : "neutral"
            }
            AppTextField {
                id: blockEditorField
                Layout.fillWidth: true
                Layout.preferredHeight: 30
                text: pane.selectedValue
                font.family: "Menlo"
                readOnly: pane.readPane
                placeholderText: "选择一个块后编辑 16 字节数据"
                Connections {
                    target: backend
                    function onSelectedDataBlockChanged() {
                        if (!pane.readPane)
                            blockEditorField.text = backend.selectedDataBlockValue
                    }
                    function onSelectedCardReadBlockChanged() {
                        if (pane.readPane)
                            blockEditorField.text = backend.selectedCardReadBlockValue
                    }
                }
            }
            AppSwitch {
                id: allowTrailerEdit
                Layout.preferredWidth: pane.readPane ? 0 : 118
                text: "允许改尾块"
                visible: !pane.readPane
                checked: false
            }
            SmallButton {
                Layout.preferredWidth: pane.readPane ? 0 : 72
                text: "保存块"
                visible: !pane.readPane
                danger: pane.selectedIsTrailer
                onClicked: backend.saveSelectedDataBlock(blockEditorField.text, allowTrailerEdit.checked)
            }
        }
        RowLayout {
            Layout.fillWidth: true
            SmallButton {
                text: pane.readPane ? "读取整卡" : "导入数据"
                onClicked: {
                    if (pane.readPane)
                        backend.runCommand("读取整卡", "hf mf dump")
                    else
                        backend.chooseDataFile()
                }
            }
            ExportDataButton {
                visible: pane.readPane
                Layout.preferredWidth: 118
                Layout.fillWidth: false
            }
            SmallButton {
                text: pane.readPane ? "复制到待写入" : "智能写入"
                hint: pane.readPane
                    ? "把左侧读到的整卡数据复制到右侧待写入区。"
                    : "先探测卡片能力，再自动选择普通 IC 或 GEN1A 写法；无法确认类型时不会写卡。"
                danger: !pane.readPane
                onClicked: {
                    if (pane.readPane)
                        backend.copyCardReadToPendingWrite()
                    else
                        backend.writeSelectedDataToCard(root.dangerUnlocked)
                }
            }
        }
    }

    component TableHeaderText: Text {
        color: root.secondaryText
        font.pixelSize: 11
        font.weight: Font.DemiBold
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    component DataTableRow: Rectangle {
        id: row
        property int blockIndex: 0
        property string label: ""
        property string value: ""
        property bool manufacturer: false
        property bool trailer: false
        property bool selected: false
        signal picked(int blockIndex)
        radius: 6
        color: selected
            ? (root.darkMode ? "#14233a" : "#eaf2ff")
            : manufacturer
                ? (root.darkMode ? "#102536" : "#edf8ff")
                : trailer
                    ? (root.darkMode ? "#2b2112" : "#fff7ed")
                    : root.buttonBg
        border.color: selected
            ? (root.darkMode ? "#4f8bd6" : "#60a5fa")
            : manufacturer
                ? (root.darkMode ? "#2d6f9f" : "#7dd3fc")
                : trailer
                    ? (root.darkMode ? "#7c5525" : "#fed7aa")
                    : root.buttonBorder
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            spacing: 8
            Text {
                text: label
                color: manufacturer ? (root.darkMode ? "#8ed0ff" : "#0369a1") : root.secondaryText
                font.family: "Menlo"
                font.pixelSize: 10
                Layout.preferredWidth: 48
                verticalAlignment: Text.AlignVCenter
            }
            Text {
                text: value
                color: root.primaryText
                font.family: "Menlo"
                font.pixelSize: 10
                elide: Text.ElideRight
                Layout.fillWidth: true
                verticalAlignment: Text.AlignVCenter
            }
            Text {
                text: manufacturer ? "UID/厂商块" : trailer ? "密钥尾块" : "数据块"
                color: manufacturer
                    ? (root.darkMode ? "#8ed0ff" : "#0369a1")
                    : trailer
                        ? (root.darkMode ? "#f0b46b" : "#9a3412")
                        : root.secondaryText
                font.pixelSize: 10
                Layout.preferredWidth: 74
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
            }
        }
        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: row.picked(row.blockIndex)
        }
    }

    component KeyMatrix: ColumnLayout {
        id: keyPanel
        property int selectedSector: 0
        property bool wideLayout: width >= 900
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        function sectorRow(sector) {
            if (backend.keyMatrix.length > sector)
                return backend.keyMatrix[sector]
            return {"keyA": "FFFFFFFFFFFF", "keyB": "FFFFFFFFFFFF", "knownA": false, "knownB": false, "candidateA": false, "candidateB": false}
        }

        function loadSelectedSector() {
            var row = sectorRow(selectedSector)
            keyAField.text = row.keyA
            keyBField.text = row.keyB
        }

        function knownCount(kind) {
            var count = 0
            for (var i = 0; i < backend.keyMatrix.length; i++) {
                if (kind === "A" && backend.keyMatrix[i].knownA)
                    count++
                if (kind === "B" && backend.keyMatrix[i].knownB)
                    count++
            }
            return count
        }

        function completeCount() {
            var count = 0
            for (var i = 0; i < backend.keyMatrix.length; i++) {
                if (backend.keyMatrix[i].knownA && backend.keyMatrix[i].knownB)
                    count++
            }
            return count
        }

        Component.onCompleted: loadSelectedSector()
        Connections {
            target: backend
            function onKeyMatrixChanged() {
                keyPanel.loadSelectedSector()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 24
            spacing: 8
            StatusPill { Layout.preferredWidth: 136; label: "Key A"; value: keyPanel.knownCount("A") + "/" + backend.keyMatrix.length; tone: keyPanel.knownCount("A") === backend.keyMatrix.length ? "green" : "neutral" }
            StatusPill { Layout.preferredWidth: 136; label: "Key B"; value: keyPanel.knownCount("B") + "/" + backend.keyMatrix.length; tone: keyPanel.knownCount("B") === backend.keyMatrix.length ? "green" : "neutral" }
            StatusPill { Layout.preferredWidth: 150; label: "完整扇区"; value: keyPanel.completeCount() + "/" + backend.keyMatrix.length; tone: keyPanel.completeCount() === backend.keyMatrix.length ? "green" : "amber" }
            Text {
                Layout.fillWidth: true
                text: "点击任意扇区可查看或修正密钥；保存密钥只保存到本地工作区，不会写卡。"
                color: root.secondaryText
                font.pixelSize: 11
                elide: Text.ElideRight
                verticalAlignment: Text.AlignVCenter
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 14

            RowLayout {
                visible: keyPanel.wideLayout
                Layout.preferredWidth: Math.max(850, keyPanel.width - 338)
                Layout.fillHeight: true
                spacing: 10
                KeyTableColumn {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    startSector: 0
                    owner: keyPanel
                    onPicked: function(sectorNumber) {
                        keyPanel.selectedSector = sectorNumber
                        keyPanel.loadSelectedSector()
                    }
                }
                KeyTableColumn {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    startSector: 8
                    owner: keyPanel
                    onPicked: function(sectorNumber) {
                        keyPanel.selectedSector = sectorNumber
                        keyPanel.loadSelectedSector()
                    }
                }
            }

            GridLayout {
                visible: !keyPanel.wideLayout
                Layout.preferredWidth: Math.min(292, keyPanel.width * 0.58)
                Layout.fillHeight: true
                columns: 4
                rowSpacing: 6
                columnSpacing: 6
                Repeater {
                    model: backend.keyMatrix
                    delegate: KeySectorCell {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        sector: modelData.sector
                        keyA: modelData.keyA
                        keyB: modelData.keyB
                        knownA: Boolean(modelData.knownA)
                        knownB: Boolean(modelData.knownB)
                        candidateA: Boolean(modelData.candidateA)
                        candidateB: Boolean(modelData.candidateB)
                        showKeys: false
                        selected: keyPanel.selectedSector === modelData.sector
                        onPicked: function(sectorNumber) {
                            keyPanel.selectedSector = sectorNumber
                            keyPanel.loadSelectedSector()
                        }
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 10
                Text {
                    Layout.fillWidth: true
                    text: "当前扇区 " + (keyPanel.selectedSector < 10 ? "0" : "") + keyPanel.selectedSector
                    color: root.primaryText
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
                RowLayout {
                    Layout.fillWidth: true
                    Text { text: "Key A"; color: root.secondaryText; font.pixelSize: 11; Layout.preferredWidth: 44 }
                    AppTextField { id: keyAField; Layout.fillWidth: true; Layout.preferredHeight: 28; placeholderText: "FFFFFFFFFFFF" }
                }
                RowLayout {
                    Layout.fillWidth: true
                    Text { text: "Key B"; color: root.secondaryText; font.pixelSize: 11; Layout.preferredWidth: 44 }
                    AppTextField { id: keyBField; Layout.fillWidth: true; Layout.preferredHeight: 28; placeholderText: "FFFFFFFFFFFF" }
                }
                GridLayout {
                    Layout.fillWidth: true
                    columns: keyPanel.wideLayout ? 3 : 2
                    rowSpacing: 8
                    columnSpacing: 8
                    SmallButton { text: "应用到扇区"; onClicked: backend.setSectorKeys(keyPanel.selectedSector, keyAField.text, keyBField.text) }
                    SmallButton { text: "默认密钥"; onClicked: { keyAField.text = "FFFFFFFFFFFF"; keyBField.text = "FFFFFFFFFFFF" } }
                    SmallButton { text: "载入密钥"; onClicked: backend.loadWorkspaceKeys() }
                    SmallButton { text: "保存密钥"; onClicked: backend.saveKeyMatrix() }
                    SmallButton { text: "清空密钥"; danger: true; onClicked: backend.clearKeyMatrix(root.dangerUnlocked) }
                    SmallButton { text: "扫默认密钥"; onClicked: backend.runCommand("默认密码扫描", "workflow mifare_default_key_scan") }
                }
            }
        }
    }

    component KeySectorCell: Rectangle {
        id: cell
        property int sector: 0
        property string keyA: "FFFFFFFFFFFF"
        property string keyB: "FFFFFFFFFFFF"
        property bool knownA: false
        property bool knownB: false
        property bool candidateA: false
        property bool candidateB: false
        property bool showKeys: false
        property bool selected: false
        signal picked(int sectorNumber)
        radius: 7
        color: selected ? (root.darkMode ? "#14233a" : "#eaf2ff") : (root.darkMode ? "#101822" : "#f8fafc")
        border.color: selected ? (root.darkMode ? "#4f8bd6" : "#60a5fa") : root.buttonBorder
        ColumnLayout {
            visible: cell.showKeys
            anchors.fill: parent
            anchors.margins: 8
            spacing: 5
            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                Text {
                    text: (sector < 10 ? "0" : "") + sector
                    color: root.primaryText
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    Layout.preferredWidth: 26
                }
                Text {
                    text: (knownA || knownB) ? "已验证" : (candidateA || candidateB) ? "待验证" : "未解析"
                    color: (knownA || knownB) ? (root.darkMode ? "#7dd7a8" : "#166534") : (candidateA || candidateB) ? (root.darkMode ? "#f0b46b" : "#9a3412") : root.secondaryText
                    font.pixelSize: 10
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignRight
                    elide: Text.ElideRight
                }
            }
            KeyLine { label: "A"; value: cell.keyA; known: cell.knownA; candidate: cell.candidateA }
            KeyLine { label: "B"; value: cell.keyB; known: cell.knownB; candidate: cell.candidateB }
        }
        ColumnLayout {
            visible: !cell.showKeys
            anchors.fill: parent
            anchors.margins: 5
            spacing: 4
            Item { Layout.fillHeight: true }
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: (sector < 10 ? "0" : "") + sector
                color: root.primaryText
                font.pixelSize: 10
                font.weight: Font.DemiBold
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 4
                KeyStatusBadge { text: "A"; known: cell.knownA; candidate: cell.candidateA }
                KeyStatusBadge { text: "B"; known: cell.knownB; candidate: cell.candidateB }
            }
            Item { Layout.fillHeight: true }
        }
        MouseArea {
            id: mouseArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: cell.picked(cell.sector)
        }
        ToolTip.visible: mouseArea.containsMouse
        ToolTip.delay: 450
        ToolTip.text: "扇区 " + (sector < 10 ? "0" : "") + sector + "\nKey A: " + keyA + (knownA ? "（已验证）" : candidateA ? "（待验证）" : "（未知）") + "\nKey B: " + keyB + (knownB ? "（已验证）" : candidateB ? "（待验证）" : "（未知）")
    }

    component KeyTableColumn: ColumnLayout {
        id: table
        property int startSector: 0
        property var owner
        signal picked(int sectorNumber)
        spacing: 4

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 22
            radius: 5
            color: root.darkMode ? "#101822" : "#f8fafc"
            border.color: root.buttonBorder
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 8
                Text { text: "扇区"; color: root.secondaryText; font.pixelSize: 10; Layout.preferredWidth: 34; verticalAlignment: Text.AlignVCenter }
                Text { text: "Key A"; color: root.secondaryText; font.pixelSize: 10; Layout.preferredWidth: 118; verticalAlignment: Text.AlignVCenter }
                Text { text: "Key B"; color: root.secondaryText; font.pixelSize: 10; Layout.preferredWidth: 118; verticalAlignment: Text.AlignVCenter }
                Text { text: "状态"; color: root.secondaryText; font.pixelSize: 10; Layout.preferredWidth: 40; horizontalAlignment: Text.AlignRight; verticalAlignment: Text.AlignVCenter }
                Item { Layout.fillWidth: true }
            }
        }

        Repeater {
            model: 8
            delegate: KeyTableRow {
                Layout.fillWidth: true
                Layout.preferredHeight: 26
                sector: table.startSector + index
                keyA: table.owner.sectorRow(sector).keyA
                keyB: table.owner.sectorRow(sector).keyB
                knownA: Boolean(table.owner.sectorRow(sector).knownA)
                knownB: Boolean(table.owner.sectorRow(sector).knownB)
                candidateA: Boolean(table.owner.sectorRow(sector).candidateA)
                candidateB: Boolean(table.owner.sectorRow(sector).candidateB)
                selected: table.owner.selectedSector === sector
                onPicked: function(sectorNumber) {
                    table.picked(sectorNumber)
                }
            }
        }

        Item { Layout.fillHeight: true }
    }

    component KeyTableRow: Rectangle {
        id: row
        property int sector: 0
        property string keyA: "FFFFFFFFFFFF"
        property string keyB: "FFFFFFFFFFFF"
        property bool knownA: false
        property bool knownB: false
        property bool candidateA: false
        property bool candidateB: false
        property bool selected: false
        signal picked(int sectorNumber)
        radius: 5
        color: selected ? (root.darkMode ? "#14233a" : "#eaf2ff") : (root.darkMode ? "#101822" : "#f8fafc")
        border.color: selected ? (root.darkMode ? "#4f8bd6" : "#60a5fa") : root.buttonBorder

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            spacing: 8
            Text {
                text: (row.sector < 10 ? "0" : "") + row.sector
                color: root.primaryText
                font.pixelSize: 11
                font.weight: Font.DemiBold
                Layout.preferredWidth: 34
                verticalAlignment: Text.AlignVCenter
            }
            KeyValueText {
                Layout.preferredWidth: 118
                value: row.keyA
                known: row.knownA
                candidate: row.candidateA
            }
            KeyValueText {
                Layout.preferredWidth: 118
                value: row.keyB
                known: row.knownB
                candidate: row.candidateB
            }
            Text {
                text: (row.knownA && row.knownB) ? "完整" : (row.knownA || row.knownB) ? "部分" : (row.candidateA || row.candidateB) ? "待验证" : "缺失"
                color: (row.knownA && row.knownB) ? (root.darkMode ? "#7dd7a8" : "#166534") : (row.candidateA || row.candidateB) ? (root.darkMode ? "#f0b46b" : "#9a3412") : root.secondaryText
                font.pixelSize: 10
                font.weight: Font.DemiBold
                Layout.preferredWidth: 40
                horizontalAlignment: Text.AlignRight
                verticalAlignment: Text.AlignVCenter
            }
            Item { Layout.fillWidth: true }
        }

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: row.picked(row.sector)
        }
    }

    component KeyValueText: Text {
        property string value: ""
        property bool known: false
        property bool candidate: false
        text: value
        color: known ? root.primaryText : candidate ? (root.darkMode ? "#f0b46b" : "#9a3412") : root.secondaryText
        font.family: "Menlo"
        font.pixelSize: 10
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    component KeyLine: Rectangle {
        property string label: ""
        property string value: ""
        property bool known: false
        property bool candidate: false
        Layout.fillWidth: true
        Layout.preferredHeight: 20
        radius: 5
        color: known ? (root.darkMode ? "#10281d" : "#ecfdf5") : candidate ? (root.darkMode ? "#2a1f12" : "#fff7ed") : (root.darkMode ? "#17202b" : "#f8fafc")
        border.color: known ? (root.darkMode ? "#2d6b4d" : "#86efac") : candidate ? (root.darkMode ? "#7c5525" : "#fed7aa") : root.buttonBorder
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 7
            anchors.rightMargin: 7
            spacing: 6
            Text {
                text: label
                color: known ? (root.darkMode ? "#7dd7a8" : "#166534") : candidate ? (root.darkMode ? "#f0b46b" : "#9a3412") : root.secondaryText
                font.pixelSize: 10
                font.weight: Font.DemiBold
                Layout.preferredWidth: 12
                verticalAlignment: Text.AlignVCenter
            }
            Text {
                text: value
                color: known ? root.primaryText : candidate ? (root.darkMode ? "#f0b46b" : "#9a3412") : root.secondaryText
                font.family: "Menlo"
                font.pixelSize: 11
                elide: Text.ElideRight
                Layout.fillWidth: true
                verticalAlignment: Text.AlignVCenter
            }
        }
    }

    component KeyStatusBadge: Rectangle {
        property string text: ""
        property bool known: false
        property bool candidate: false
        Layout.fillWidth: true
        Layout.preferredHeight: 18
        radius: 5
        color: known ? (root.darkMode ? "#10281d" : "#ecfdf5") : candidate ? (root.darkMode ? "#2a1f12" : "#fff7ed") : (root.darkMode ? "#17202b" : "#f8fafc")
        border.color: known ? (root.darkMode ? "#2d6b4d" : "#86efac") : candidate ? (root.darkMode ? "#7c5525" : "#fed7aa") : root.buttonBorder
        Text {
            anchors.centerIn: parent
            text: parent.text
            color: known ? (root.darkMode ? "#7dd7a8" : "#166534") : candidate ? (root.darkMode ? "#f0b46b" : "#9a3412") : root.secondaryText
            font.pixelSize: 10
            font.weight: Font.DemiBold
        }
    }

    component SectorMiniPanel: ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 6
        Text {
            Layout.fillWidth: true
            Layout.preferredHeight: 26
            text: "只在你明确知道扇区号、Key A/B 和要操作的块时使用。普通复制不用来这里。"
            color: root.secondaryText
            font.pixelSize: 11
            wrapMode: Text.WordWrap
            lineHeight: 1.05
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            AppTextField { id: miniSector; Layout.preferredWidth: 58; Layout.preferredHeight: 26; text: "0"; placeholderText: "扇区" }
            AppTextField { id: miniBlock; Layout.preferredWidth: 58; Layout.preferredHeight: 26; text: "3"; placeholderText: "块" }
            AppComboBox { id: miniKeyType; Layout.preferredWidth: 60; Layout.preferredHeight: 26; model: ["A", "B"] }
            AppTextField { id: miniKey; Layout.fillWidth: true; Layout.preferredHeight: 26; text: "FFFFFFFFFFFF"; placeholderText: "密钥" }
        }
        AppTextField {
            id: miniData
            Layout.fillWidth: true
            Layout.preferredHeight: 26
            placeholderText: "写块数据：32 位十六进制"
        }
        GridLayout {
            Layout.fillWidth: true
            columns: 2
            rowSpacing: 6
            columnSpacing: 8
            SmallButton { Layout.preferredHeight: 28; text: "读取扇区"; onClicked: backend.readMifareSector(miniSector.text, miniKeyType.currentText, miniKey.text) }
            SmallButton { Layout.preferredHeight: 28; text: "读取指定块"; onClicked: backend.readMifareBlock(miniSector.text, miniBlock.text, miniKeyType.currentText, miniKey.text) }
            SmallButton { Layout.preferredHeight: 28; text: "写入指定块"; danger: true; onClicked: backend.writeMifareBlock(root.dangerUnlocked, miniSector.text, miniBlock.text, miniKeyType.currentText, miniKey.text, miniData.text) }
            SmallButton { Layout.preferredHeight: 28; text: "填默认密钥"; onClicked: miniKey.text = "FFFFFFFFFFFF" }
        }
    }

    component SectorPanel: ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 4
        RowLayout {
            Layout.fillWidth: true
            AppTextField { id: sectorField; Layout.preferredWidth: 58; Layout.preferredHeight: 25; text: "0"; placeholderText: "扇区" }
            AppComboBox { id: keyType; Layout.preferredWidth: 72; Layout.preferredHeight: 25; model: ["A", "B"] }
            AppTextField { id: keyField; Layout.fillWidth: true; Layout.preferredHeight: 25; text: "FFFFFFFFFFFF"; placeholderText: "密钥" }
        }
        RowLayout {
            Layout.fillWidth: true
            SmallButton { text: "读取扇区"; onClicked: backend.readMifareSector(sectorField.text, keyType.currentText, keyField.text) }
            SmallButton { text: "写入扇区"; danger: true; onClicked: backend.writeMifareSector(root.dangerUnlocked, sectorField.text, keyType.currentText, keyField.text, block0Field.text, block1Field.text, block2Field.text, block3Field.text) }
        }
        GridLayout {
            Layout.fillWidth: true
            columns: 2
            rowSpacing: 4
            columnSpacing: 6
            AppTextField { id: block0Field; Layout.fillWidth: true; Layout.preferredHeight: 24; text: ""; placeholderText: "块0：32 位十六进制" }
            AppTextField { id: block1Field; Layout.fillWidth: true; Layout.preferredHeight: 24; text: ""; placeholderText: "块1：32 位十六进制" }
            AppTextField { id: block2Field; Layout.fillWidth: true; Layout.preferredHeight: 24; text: ""; placeholderText: "块2：32 位十六进制" }
            AppTextField { id: block3Field; Layout.fillWidth: true; Layout.preferredHeight: 24; text: ""; placeholderText: "块3：32 位十六进制" }
        }
        RowLayout {
            Layout.fillWidth: true
            SmallButton { text: "读取尾块"; onClicked: backend.readMifareBlock(sectorField.text, "3", keyType.currentText, keyField.text) }
            SmallButton { text: "写入尾块"; danger: true; onClicked: backend.writeMifareBlock(root.dangerUnlocked, sectorField.text, "3", keyType.currentText, keyField.text, block3Field.text) }
            SmallButton { text: "秘钥默认"; onClicked: keyField.text = "FFFFFFFFFFFF" }
        }
    }

    component WriteCardGuidePanel: ColumnLayout {
        id: guide
        readonly property bool compact: height < 150
        readonly property int buttonColumns: width >= 560 ? 4 : width >= 390 ? 3 : 2
        readonly property int buttonHeight: compact ? 22 : 27
        anchors.fill: parent
        anchors.margins: compact ? 6 : 8
        spacing: compact ? 3 : 5

        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            AppTextField {
                id: rescueUid
                Layout.fillWidth: true
                Layout.preferredHeight: guide.compact ? 22 : 28
                placeholderText: "重置后卡号，如 9D7456AA"
                maximumLength: 14
                inputMethodHints: Qt.ImhUppercaseOnly | Qt.ImhPreferUppercase | Qt.ImhNoPredictiveText
            }
            AppSwitch {
                Layout.preferredWidth: guide.compact ? 88 : 100
                text: "允许危险操作"
                checked: root.dangerUnlocked
                onToggled: root.dangerUnlocked = checked
            }
        }

        CompactInfoLine {
            text: "待写入：" + backend.dataWorkspaceText
        }

        GridLayout {
            Layout.fillWidth: true
            columns: guide.buttonColumns
            rowSpacing: guide.compact ? 3 : 6
            columnSpacing: 6

            SmallButton {
                Layout.preferredHeight: guide.buttonHeight
                text: "校验数据"
                hint: "检查待写入数据、密钥和写卡计划是否完整。"
                onClicked: backend.verifyWorkspaceData()
            }
            SmallButton {
                Layout.preferredHeight: guide.buttonHeight
                text: "普通IC写入"
                danger: true
                hint: "写普通数据块和密钥尾块，保留目标卡自己的块 00 / UID。"
                onClicked: backend.writeSelectedDataToCard(root.dangerUnlocked)
            }
            SmallButton {
                Layout.preferredHeight: guide.buttonHeight
                text: "GEN1A写入"
                danger: true
                hint: "给支持后门的魔术卡整卡写入，可写 0 块。"
                onClicked: backend.writeSelectedDataToMagicCard(root.dangerUnlocked)
            }
            SmallButton {
                Layout.preferredHeight: guide.buttonHeight
                text: "读取UID"
                hint: "读取当前卡 UID 和基础卡型信息。"
                onClicked: backend.runCommand("读取UID", "hf 14a reader")
            }
            SmallButton {
                Layout.preferredHeight: guide.buttonHeight
                text: "一键重置"
                danger: true
                hint: "自动执行坏卡救援、恢复 UID、写入空白结构并校验。"
                onClicked: backend.oneClickResetMagicCard(root.dangerUnlocked, rescueUid.text)
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: guide.compact ? 0 : 58
            visible: !guide.compact
            radius: 8
            color: root.darkMode ? "#121a23" : "#f8fbff"
            border.color: root.panelBorder
            Text {
                anchors.fill: parent
                anchors.margins: 9
                text: "普通IC写入：写数据和密钥，保留目标卡 UID。\nGEN1A写入：执行前先检测后门，用于复制块 00 / UID。\n只差块 00 时，说明其余卡片数据已经写入成功。"
                color: root.secondaryText
                font.pixelSize: 11
                wrapMode: Text.WordWrap
                lineHeight: 1.08
                verticalAlignment: Text.AlignVCenter
            }
        }
    }

    component WriteModeButton: Rectangle {
        id: modeButton
        property string text: ""
        property bool selected: false
        signal clicked()
        Layout.fillWidth: true
        Layout.preferredHeight: 28
        radius: 7
        color: selected ? (root.darkMode ? "#14233a" : "#eaf2ff") : root.buttonBg
        border.color: selected ? (root.darkMode ? "#4f8bd6" : "#60a5fa") : root.buttonBorder
        Text {
            anchors.fill: parent
            anchors.leftMargin: 6
            anchors.rightMargin: 6
            text: modeButton.text
            color: modeButton.selected ? (root.darkMode ? "#9fcbff" : "#1d4ed8") : root.primaryText
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            font.pixelSize: 12
            font.weight: Font.DemiBold
            elide: Text.ElideRight
        }
        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: modeButton.clicked()
        }
    }

    component CompactInfoLine: Text {
        Layout.fillWidth: true
        Layout.preferredHeight: 13
        text: ""
        color: root.secondaryText
        font.pixelSize: 11
        elide: Text.ElideRight
        verticalAlignment: Text.AlignVCenter
    }

    component MagicMaintenancePanel: ColumnLayout {
        id: magicPanel
        anchors.fill: parent
        anchors.margins: 10
        spacing: 6

        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            AppTextField {
                id: advancedUid
                Layout.fillWidth: true
                Layout.preferredHeight: 26
                placeholderText: "目标UID，如 9D7456AA"
                maximumLength: 14
                inputMethodHints: Qt.ImhUppercaseOnly | Qt.ImhPreferUppercase | Qt.ImhNoPredictiveText
            }
            AppSwitch {
                Layout.preferredWidth: 92
                text: "允许危险操作"
                checked: root.dangerUnlocked
                onToggled: root.dangerUnlocked = checked
            }
        }

        Text {
            Layout.fillWidth: true
            Layout.preferredHeight: 28
            text: "主界面用「一键重置」。这里保留拆步功能，方便排查卡坏在哪一步。"
            color: root.secondaryText
            font.pixelSize: 11
            wrapMode: Text.WordWrap
            lineHeight: 1.05
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 3
            rowSpacing: 6
            columnSpacing: 6
            SmallButton {
                Layout.preferredHeight: 28
                text: "一键重置"
                danger: true
                hint: "救援、恢复 UID、初始化、校验一次完成。"
                onClicked: backend.oneClickResetMagicCard(root.dangerUnlocked, advancedUid.text)
            }
            SmallButton {
                Layout.preferredHeight: 28
                text: "坏卡救援"
                danger: true
                hint: "把异常 GEN1A 卡先拉回能识别的状态。"
                onClicked: backend.rescueMagicCard(root.dangerUnlocked)
            }
            SmallButton {
                Layout.preferredHeight: 28
                text: "恢复UID"
                danger: true
                hint: "用上方 UID 写回卡号。"
                onClicked: backend.restoreMagicCardUid(root.dangerUnlocked, advancedUid.text)
            }
            SmallButton {
                Layout.preferredHeight: 28
                text: "默认初始化"
                danger: true
                hint: "用上方 UID 清空为默认 S50。"
                onClicked: backend.resetMagicCardToBlank(root.dangerUnlocked, advancedUid.text)
            }
            SmallButton {
                Layout.preferredHeight: 28
                text: "读取UID"
                onClicked: backend.runCommand("读取UID", "hf 14a reader")
            }
            SmallButton {
                Layout.preferredHeight: 28
                text: "GEN1A写入"
                danger: true
                hint: "把待写入数据整卡写入 GEN1A 魔术卡。"
                onClicked: backend.writeSelectedDataToMagicCard(root.dangerUnlocked)
            }
        }
    }

    component AdvancedDevicePanel: ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 6

        GridLayout {
            Layout.fillWidth: true
            columns: root.compactMode ? 3 : 2
            rowSpacing: 3
            columnSpacing: 10
            CompactInfoLine { text: "串口：" + (backend.selectedPort || "未选择") }
            CompactInfoLine { text: "设备：" + backend.deviceText }
            CompactInfoLine { text: "固件：" + backend.firmwareText }
            CompactInfoLine { text: "版本：v" + backend.appVersion + " / " + backend.appBuild }
            CompactInfoLine { text: "校验：" + backend.integrityText }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 3
            rowSpacing: 6
            columnSpacing: 6
            SmallButton { Layout.preferredHeight: 28; text: "读取版本"; onClicked: backend.runCommand("读取设备版本", "hw version") }
            SmallButton { Layout.preferredHeight: 28; text: "测试通信"; onClicked: backend.runCommand("测试通信", "hw ping") }
            SmallButton { Layout.preferredHeight: 28; text: "设备状态"; onClicked: backend.runCommand("设备状态", "hw status") }
            SmallButton { Layout.preferredHeight: 28; text: "清除日志"; onClicked: backend.clearLog() }
            SmallButton { Layout.preferredHeight: 28; text: "打开工作区"; onClicked: backend.openWorkspaceFolder() }
            SmallButton { Layout.preferredHeight: 28; text: "天线电压"; onClicked: backend.runCommand("天线电压", "hw tune") }
        }
    }

    component QuickCommandPanel: GridLayout {
        anchors.fill: parent
        anchors.margins: 12
        columns: 4
        rowSpacing: 8
        columnSpacing: 8
        SmallButton { text: "清除日志"; onClicked: backend.clearLog() }
        SmallButton { text: "测试通信"; onClicked: backend.runCommand("测试通信", "hw ping") }
        SmallButton { text: "读取版本"; onClicked: backend.runCommand("读取设备版本", "hw version") }
        SmallButton { text: "设备状态"; onClicked: backend.runCommand("设备状态", "hw status") }
    }

    component CommandPanel: RowLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10
        AppTextField {
            id: customCommand
            Layout.fillWidth: true
            text: "hf search"
            placeholderText: "输入 PM3 命令"
            Keys.onReturnPressed: backend.runAuthorizedCommand("自定义命令", customCommand.text, root.dangerUnlocked)
        }
        HeaderButton {
            text: "执行"
            Layout.preferredWidth: 96
            onClicked: backend.runAuthorizedCommand("自定义命令", customCommand.text, root.dangerUnlocked)
        }
    }

    component MyKeyLibraryPanel: ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 8

        Text {
            Layout.fillWidth: true
            text: "手动输入 12 位十六进制密钥，或把当前已解析出的密钥保存进个人库。"
            color: root.secondaryText
            font.pixelSize: 11
            wrapMode: Text.WordWrap
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            AppTextField {
                id: personalKeyInput
                Layout.fillWidth: true
                placeholderText: "例如 FFFFFFFFFFFF"
                maximumLength: 24
                Keys.onReturnPressed: backend.addPersonalKey(personalKeyInput.text)
            }
            SmallButton {
                text: "加入我的库"
                Layout.preferredWidth: 110
                onClicked: backend.addPersonalKey(personalKeyInput.text)
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            SmallButton { text: "保存当前密钥"; onClicked: backend.saveCurrentKeysToPersonalLibrary() }
            SmallButton { text: "打开本地库"; onClicked: backend.openKeyLibraryFolder() }
        }
    }

    component DeviceInfoPanel: ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10
        InfoLine { label: "串口"; value: backend.selectedPort || "未选择" }
        InfoLine { label: "设备"; value: backend.deviceText }
        InfoLine { label: "固件"; value: backend.firmwareText }
        InfoLine { label: "版本"; value: "v" + backend.appVersion + " / " + backend.appBuild }
        InfoLine { label: "校验"; value: backend.integrityText }
        InfoLine { label: "字典"; value: backend.dictionaryText }
        RowLayout {
            Layout.fillWidth: true
            SmallButton { text: "读取版本"; onClicked: backend.runCommand("读取设备版本", "hw version") }
            SmallButton { text: "设备状态"; onClicked: backend.runCommand("设备状态", "hw status") }
        }
    }

    component SafetyPanel: ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10
        AppSwitch {
            text: "允许危险操作（写卡、改 UID、擦卡等）"
            checked: root.dangerUnlocked
            onToggled: root.dangerUnlocked = checked
        }
        StatusPill {
            Layout.fillWidth: true
            label: "保护"
            value: root.dangerUnlocked ? "已打开危险操作" : "危险操作已锁定"
            tone: root.dangerUnlocked ? "rose" : "green"
        }
        Text {
            Layout.fillWidth: true
            text: "请仅在自有或已获明确授权的卡片与设备上使用。"
            color: root.secondaryText
            font.pixelSize: 11
            wrapMode: Text.WordWrap
        }
    }

    component InfoLine: RowLayout {
        property string label: ""
        property string value: ""
        Layout.fillWidth: true
        Text {
            text: label
            color: root.secondaryText
            font.pixelSize: 12
            Layout.preferredWidth: 44
        }
        Text {
            text: value
            color: root.primaryText
            font.pixelSize: 12
            elide: Text.ElideRight
            Layout.fillWidth: true
        }
    }
}
