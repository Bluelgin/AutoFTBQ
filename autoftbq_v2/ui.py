"""PySide6 workspace for the AutoFTBQ v2 direction prototype."""

from __future__ import annotations

from html import escape
import json
import os

from PySide6.QtCore import QPointF, Qt, QThread, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ai_clients import create_chat_client
from ai_module import import_json_to_snbt
import mod_scanner
from quest_tools import QuestToolbox

from .agent import ProjectAgent
from .asset_index import AssetIndex
from .project import ProjectStore, QuestBookProject


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_FILTER = "AutoFTBQ Project (*.autoftbq.json);;JSON (*.json)"


class AgentThread(QThread):
    answered = Signal(str)
    failed = Signal(str)
    action = Signal(str, str)

    def __init__(self, agent: ProjectAgent, prompt: str):
        super().__init__()
        self.agent = agent
        self.prompt = prompt

    def run(self):
        self.agent.on_action = self._on_action
        try:
            self.answered.emit(self.agent.run(self.prompt))
        except Exception as exc:
            self.failed.emit(str(exc) or type(exc).__name__)

    def _on_action(self, name, arguments, result):
        detail = json.dumps(arguments, ensure_ascii=False)
        self.action.emit(name, detail)


class QuestNode(QGraphicsRectItem):
    WIDTH = 190
    HEIGHT = 82

    def __init__(self, quest, x: float, y: float, icon_path: str = ""):
        super().__init__(0, 0, self.WIDTH, self.HEIGHT)
        self.quest = quest
        self.setData(0, quest.id)
        self.setPos(x, y)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, True)
        task_type = quest.tasks[0].type if quest.tasks else "checkmark"
        colors = {
            "item": "#d9efe9",
            "kill": "#f5ded5",
            "dimension": "#dce8f4",
            "advancement": "#f3e7c5",
        }
        self.setBrush(QBrush(QColor(colors.get(task_type, "#eee9df"))))
        self.setPen(QPen(QColor("#a9a398"), 1.4))
        title = quest.title[:22] + ("..." if len(quest.title) > 22 else "")
        target = quest.tasks[0].target if quest.tasks else ""
        text_x = 14
        if icon_path:
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                from PySide6.QtWidgets import QGraphicsPixmapItem

                self.icon_item = QGraphicsPixmapItem(
                    pixmap.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation),
                    self,
                )
                self.icon_item.setPos(12, 20)
                text_x = 62
        self.title_item = self.scene_text(title, 13, True, QPointF(text_x, 12))
        self.detail_item = self.scene_text(target or task_type, 9, False, QPointF(text_x, 44))

    def scene_text(self, text, size, bold, pos):
        from PySide6.QtWidgets import QGraphicsSimpleTextItem

        item = QGraphicsSimpleTextItem(text, self)
        item.setFont(QFont("Microsoft YaHei UI", size, QFont.Weight.DemiBold if bold else QFont.Weight.Normal))
        item.setBrush(QBrush(QColor("#242824" if bold else "#667069")))
        item.setPos(pos)
        return item

    def itemChange(self, change, value):
        if change == QGraphicsRectItem.GraphicsItemChange.ItemSelectedChange:
            self.setPen(QPen(QColor("#19715a") if value else QColor("#a9a398"), 2.2 if value else 1.4))
        return super().itemChange(change, value)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.store = ProjectStore(self._starter_project())
        self.project_path = ""
        self.toolbox = QuestToolbox()
        self.asset_index = None
        self.agent = None
        self.agent_thread = None
        self.current_chapter_id = ""
        self.current_quest_id = ""
        self.connect_mode = False
        self.connection_source_id = ""
        self.setWindowTitle("AutoFTBQ v2 - Agent Workspace")
        self.resize(1460, 900)
        self.setMinimumSize(1100, 700)
        self._build_ui()
        self._apply_style()
        self.refresh_all()

    @staticmethod
    def _starter_project():
        store = ProjectStore(QuestBookProject(title="新的整合包任务书"))
        chapter = store.create_chapter("开始规划", "minecraft:writable_book")
        store.add_quest(
            chapter.id,
            "告诉 Agent 你的目标",
            "在右侧描述整合包玩法，Agent 会通过工具逐步编辑这里。",
            "checkmark",
        )
        store._undo.clear()
        return store.project

    def _build_ui(self):
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._build_sidebar())
        root_layout.addWidget(self._build_main_area(), 1)
        self.setCentralWidget(root)

    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(300)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(20, 22, 20, 18)
        layout.setSpacing(12)

        brand_row = QHBoxLayout()
        logo = QLabel("A2")
        logo.setObjectName("logo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFixedSize(42, 42)
        brand = QVBoxLayout()
        name = QLabel("AutoFTBQ")
        name.setObjectName("brandName")
        branch = QLabel("v2 Agent Workspace")
        branch.setObjectName("sidebarMuted")
        brand.addWidget(name)
        brand.addWidget(branch)
        brand_row.addWidget(logo)
        brand_row.addLayout(brand)
        brand_row.addStretch()
        layout.addLayout(brand_row)

        step_label = QLabel("第一步")
        step_label.setObjectName("sidebarLabel")
        layout.addWidget(step_label)
        pack_card = QFrame()
        pack_card.setObjectName("packCard")
        pack_layout = QVBoxLayout(pack_card)
        pack_layout.setContentsMargins(12, 12, 12, 12)
        choose_pack = QPushButton("选择整合包")
        choose_pack.setObjectName("packButton")
        choose_pack.clicked.connect(self.scan_modpack)
        self.modpack_status = QLabel("尚未选择。将读取物品 ID、配方与图标。")
        self.modpack_status.setWordWrap(True)
        self.modpack_status.setObjectName("packStatus")
        pack_layout.addWidget(choose_pack)
        pack_layout.addWidget(self.modpack_status)
        layout.addWidget(pack_card)

        self.project_title = QLineEdit()
        self.project_title.setObjectName("sidebarProjectTitle")
        self.project_title.editingFinished.connect(self.save_project_title)
        layout.addWidget(self.project_title)

        project_buttons = QHBoxLayout()
        for text, callback in (("新建", self.new_project), ("打开", self.open_project), ("保存", self.save_project)):
            button = QPushButton(text)
            button.clicked.connect(callback)
            project_buttons.addWidget(button)
        layout.addLayout(project_buttons)

        nav_label = QLabel("功能区")
        nav_label.setObjectName("sidebarLabel")
        layout.addWidget(nav_label)
        self.nav_buttons = []
        for text, detail, callback in (
            ("Agent 对话", "查看思考结果与行动记录", lambda: self.switch_view(0)),
            ("任务书编辑器", "节点、连线与任务属性", lambda: self.switch_view(1)),
            ("扫描整合包", "建立物品与配方索引", self.scan_modpack),
            ("检查任务书", "定位结构和 ID 问题", self.show_validation),
            ("导出 SNBT", "写入 FTB Quests 目录", self.export_snbt),
        ):
            button = QPushButton(f"{text}\n{detail}")
            button.setObjectName("navButton")
            button.setProperty("viewButton", callback.__name__ == "<lambda>")
            button.clicked.connect(callback)
            layout.addWidget(button)
            self.nav_buttons.append(button)

        chapter_row = QHBoxLayout()
        chapter_label = QLabel("章节")
        chapter_label.setObjectName("sidebarLabel")
        add = QPushButton("+")
        add.setFixedWidth(34)
        add.clicked.connect(self.add_chapter)
        chapter_row.addWidget(chapter_label)
        chapter_row.addStretch()
        chapter_row.addWidget(add)
        layout.addLayout(chapter_row)
        self.chapter_list = QListWidget()
        self.chapter_list.setObjectName("sidebarChapters")
        self.chapter_list.currentItemChanged.connect(self.select_chapter)
        layout.addWidget(self.chapter_list, 1)
        return sidebar

    def _build_main_area(self):
        panel = QFrame()
        panel.setObjectName("mainArea")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(14)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        eyebrow = QLabel("ACTIVE WORKSPACE")
        eyebrow.setObjectName("eyebrow")
        self.view_title = QLabel("与 Agent 一起制作任务书")
        self.view_title.setObjectName("viewTitle")
        titles.addWidget(eyebrow)
        titles.addWidget(self.view_title)
        header.addLayout(titles)
        header.addStretch()
        self.model_label = QLabel("读取 1.x API 配置 · 白名单工具模式")
        self.model_label.setObjectName("mainMuted")
        self.agent_state = QLabel("待命")
        self.agent_state.setObjectName("statusPill")
        header.addWidget(self.model_label)
        header.addWidget(self.agent_state)
        layout.addLayout(header)

        self.view_stack = QStackedWidget()
        self.view_stack.addWidget(self._build_conversation_view())
        self.view_stack.addWidget(self._build_editor())
        layout.addWidget(self.view_stack, 1)
        layout.addWidget(self._build_composer())
        self.switch_view(0)
        return panel

    def _build_conversation_view(self):
        page = QFrame()
        page.setObjectName("conversationCard")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 16)
        layout.setSpacing(10)
        self.chat = QTextBrowser()
        self.chat.setObjectName("chat")
        self.chat.setOpenExternalLinks(True)
        layout.addWidget(self.chat, 1)
        self.append_chat("agent", "我是项目 Agent。先扫描整合包，然后告诉我想制作什么；我的每一步操作都会显示在行动记录中。")
        action_row = QHBoxLayout()
        action_title = QLabel("行动记录")
        action_title.setObjectName("sectionTitle")
        action_hint = QLabel("这里显示 Agent 实际调用的工具，而不是隐藏的提示词")
        action_hint.setObjectName("mainMuted")
        action_row.addWidget(action_title)
        action_row.addWidget(action_hint)
        action_row.addStretch()
        layout.addLayout(action_row)
        self.action_list = QListWidget()
        self.action_list.setObjectName("actionList")
        self.action_list.setMaximumHeight(170)
        layout.addWidget(self.action_list)
        return page

    def _build_composer(self):
        composer = QFrame()
        composer.setObjectName("composer")
        layout = QVBoxLayout(composer)
        layout.setContentsMargins(16, 13, 16, 12)
        self.prompt = QTextEdit()
        self.prompt.setObjectName("prompt")
        self.prompt.setPlaceholderText("描述你想要的结果。Agent 会根据当前视图选择合适工具，例如查询物品、修改任务或运行检查。")
        self.prompt.setMaximumHeight(92)
        layout.addWidget(self.prompt)
        row = QHBoxLayout()
        self.prompt_mode = QLabel("自动选择工具")
        self.prompt_mode.setObjectName("modePill")
        hint = QLabel("Ctrl + Enter 发送")
        hint.setObjectName("mainMuted")
        self.send_button = QPushButton("交给 Agent")
        self.send_button.setObjectName("agentButton")
        self.send_button.clicked.connect(self.send_to_agent)
        row.addWidget(self.prompt_mode)
        row.addWidget(hint)
        row.addStretch()
        row.addWidget(self.send_button)
        layout.addLayout(row)
        self.send_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.send_shortcut.activated.connect(self.send_to_agent)
        return composer

    def _build_rail(self):
        rail = QFrame()
        rail.setObjectName("rail")
        rail.setFixedWidth(76)
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(12, 20, 12, 20)
        logo = QLabel("A2")
        logo.setObjectName("logo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)
        layout.addSpacing(28)
        for text, tip, callback in (
            ("书", "任务书项目", self.refresh_all),
            ("扫", "扫描整合包", self.scan_modpack),
            ("检", "检查任务书", self.run_validation),
            ("出", "导出 SNBT", self.export_snbt),
        ):
            button = QToolButton()
            button.setText(text)
            button.setToolTip(tip)
            button.clicked.connect(callback)
            layout.addWidget(button)
        layout.addStretch()
        version = QLabel("v2\nMVP")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setObjectName("railVersion")
        layout.addWidget(version)
        return rail

    def _build_workspace(self):
        panel = QFrame()
        panel.setObjectName("workspace")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 20, 18, 18)
        layout.setSpacing(14)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        eyebrow = QLabel("QUEST BOOK WORKSPACE")
        eyebrow.setObjectName("eyebrow")
        self.project_title = QLineEdit()
        self.project_title.setObjectName("projectTitle")
        self.project_title.editingFinished.connect(self.save_project_title)
        titles.addWidget(eyebrow)
        titles.addWidget(self.project_title)
        header.addLayout(titles, 1)
        for text, callback in (("新建", self.new_project), ("打开", self.open_project), ("保存", self.save_project)):
            button = QPushButton(text)
            button.clicked.connect(callback)
            header.addWidget(button)
        layout.addLayout(header)

        content = QSplitter(Qt.Orientation.Horizontal)
        content.setChildrenCollapsible(False)
        content.addWidget(self._build_chapter_panel())
        content.addWidget(self._build_editor())
        content.setSizes([245, 720])
        layout.addWidget(content, 1)
        return panel

    def _build_chapter_panel(self):
        frame = QFrame()
        frame.setObjectName("sideCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 16, 14, 14)
        row = QHBoxLayout()
        label = QLabel("章节")
        label.setObjectName("sectionTitle")
        add = QPushButton("+")
        add.setFixedWidth(34)
        add.clicked.connect(self.add_chapter)
        row.addWidget(label)
        row.addStretch()
        row.addWidget(add)
        layout.addLayout(row)
        self.chapter_list = QListWidget()
        self.chapter_list.currentItemChanged.connect(self.select_chapter)
        layout.addWidget(self.chapter_list, 1)
        self.modpack_status = QLabel("尚未扫描整合包")
        self.modpack_status.setWordWrap(True)
        self.modpack_status.setObjectName("muted")
        layout.addWidget(self.modpack_status)
        scan = QPushButton("选择并扫描整合包")
        scan.clicked.connect(self.scan_modpack)
        layout.addWidget(scan)
        return frame

    def _build_editor(self):
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        toolbar = QHBoxLayout()
        self.chapter_heading = QLabel("章节画布")
        self.chapter_heading.setObjectName("sectionTitle")
        toolbar.addWidget(self.chapter_heading)
        self.connection_hint = QLabel("普通选择模式")
        self.connection_hint.setObjectName("mainMuted")
        toolbar.addWidget(self.connection_hint)
        toolbar.addStretch()
        self.connect_button = QPushButton("连线模式")
        self.connect_button.setCheckable(True)
        self.connect_button.toggled.connect(self.toggle_connect_mode)
        add = QPushButton("添加任务")
        add.clicked.connect(self.add_quest)
        undo = QPushButton("撤销")
        undo.clicked.connect(self.undo)
        redo = QPushButton("重做")
        redo.clicked.connect(self.redo)
        toolbar.addWidget(self.connect_button)
        toolbar.addWidget(add)
        toolbar.addWidget(undo)
        toolbar.addWidget(redo)
        layout.addLayout(toolbar)

        self.scene = QGraphicsScene(self)
        self.scene.selectionChanged.connect(self.select_canvas_quest)
        self.canvas = QGraphicsView(self.scene)
        self.canvas.setObjectName("canvas")
        self.canvas.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.canvas.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        layout.addWidget(self.canvas, 3)

        self.editor_tabs = QTabWidget()
        self.editor_tabs.addTab(self._build_inspector(), "任务属性")
        self.editor_tabs.addTab(self._build_validation_panel(), "检查结果")
        layout.addWidget(self.editor_tabs, 2)
        return frame

    def _build_inspector(self):
        panel = QWidget()
        form = QFormLayout(panel)
        form.setContentsMargins(18, 16, 18, 16)
        self.quest_title = QLineEdit()
        self.quest_type = QLineEdit()
        self.quest_target = QLineEdit()
        self.quest_count = QSpinBox()
        self.quest_count.setRange(1, 999999)
        self.quest_description = QTextEdit()
        self.quest_description.setMaximumHeight(76)
        form.addRow("标题", self.quest_title)
        form.addRow("任务类型", self.quest_type)
        form.addRow("目标 ID", self.quest_target)
        form.addRow("数量", self.quest_count)
        form.addRow("描述", self.quest_description)
        row = QWidget()
        buttons = QHBoxLayout(row)
        buttons.setContentsMargins(0, 0, 0, 0)
        save = QPushButton("应用修改")
        save.setObjectName("primaryButton")
        save.clicked.connect(self.apply_quest_changes)
        remove = QPushButton("删除任务")
        remove.setObjectName("dangerButton")
        remove.clicked.connect(self.remove_quest)
        buttons.addWidget(save)
        buttons.addWidget(remove)
        buttons.addStretch()
        form.addRow("", row)
        return panel

    def _build_validation_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        row = QHBoxLayout()
        row.addWidget(QLabel("本地确定性检查，不消耗 Token"))
        row.addStretch()
        button = QPushButton("立即检查")
        button.clicked.connect(self.run_validation)
        row.addWidget(button)
        layout.addLayout(row)
        self.validation_list = QListWidget()
        layout.addWidget(self.validation_list)
        return panel

    def _build_agent_panel(self):
        panel = QFrame()
        panel.setObjectName("agentPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 18)
        layout.setSpacing(12)
        title_row = QHBoxLayout()
        title = QLabel("Agent")
        title.setObjectName("agentTitle")
        self.agent_state = QLabel("待命")
        self.agent_state.setObjectName("statusPill")
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(self.agent_state)
        layout.addLayout(title_row)
        self.model_label = QLabel("将使用 1.x 的本地 API 配置；AI 只能调用白名单工具")
        self.model_label.setObjectName("agentMuted")
        self.model_label.setWordWrap(True)
        layout.addWidget(self.model_label)

        self.chat = QTextBrowser()
        self.chat.setObjectName("chat")
        self.chat.setOpenExternalLinks(True)
        layout.addWidget(self.chat, 3)
        self.append_chat("agent", "我是项目 Agent。先扫描整合包，然后告诉我想制作什么；我的每一步操作都会显示在下面。")

        action_title = QLabel("行动记录")
        action_title.setObjectName("sectionTitleLight")
        layout.addWidget(action_title)
        self.action_list = QListWidget()
        self.action_list.setMaximumHeight(150)
        self.action_list.setObjectName("actionList")
        layout.addWidget(self.action_list)

        self.prompt = QTextEdit()
        self.prompt.setObjectName("prompt")
        self.prompt.setPlaceholderText("例如：为机械动力创建一个入门章节，先查询真实物品，再添加 5 个任务并检查结果。")
        self.prompt.setMaximumHeight(110)
        layout.addWidget(self.prompt)
        self.send_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.send_shortcut.activated.connect(self.send_to_agent)
        send_row = QHBoxLayout()
        hint = QLabel("Ctrl + Enter 发送")
        hint.setObjectName("agentMuted")
        self.send_button = QPushButton("交给 Agent")
        self.send_button.setObjectName("agentButton")
        self.send_button.clicked.connect(self.send_to_agent)
        send_row.addWidget(hint)
        send_row.addStretch()
        send_row.addWidget(self.send_button)
        layout.addLayout(send_row)
        return panel

    def _apply_style(self):
        self.setStyleSheet("""
            * { font-family: 'Microsoft YaHei UI'; font-size: 13px; }
            QMainWindow, #mainArea { background: #f3f1eb; color: #202520; }
            #sidebar { background: #1d2824; color: #edf2ef; border: none; }
            #logo { background: #d7f05c; color: #1e2925; border-radius: 13px; font-size: 16px; font-weight: 800; }
            #brandName { color: white; font-size: 18px; font-weight: 800; }
            #sidebarMuted { color: #899b93; font-size: 10px; }
            #sidebarLabel { color: #a9b7b0; font-size: 11px; font-weight: 700; margin-top: 8px; }
            #packCard { background: #263b33; border: 1px solid #527264; border-radius: 11px; }
            #packButton { background: #d7f05c; color: #1d2824; border: none; font-weight: 800; }
            #packStatus { color: #d5e2db; font-size: 10px; }
            #sidebarProjectTitle { background: #283630; color: white; border: 1px solid #3b4a44; font-size: 16px; font-weight: 700; padding: 9px; }
            #sidebar QPushButton { background: #283630; color: #dce5e0; border: 1px solid #3b4a44; }
            #sidebar QPushButton:hover { background: #34453e; border-color: #647c71; }
            #navButton { text-align: left; min-height: 45px; padding: 9px 12px; font-weight: 600; }
            #sidebarChapters { background: #202d28; color: #dce5e0; border: 1px solid #34443d; }
            #sidebarChapters::item:selected { background: #3b5148; color: white; }
            #eyebrow { color: #7b847c; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
            #viewTitle { color: #202520; font-size: 24px; font-weight: 800; }
            #mainMuted { color: #59645d; font-size: 10px; }
            #sectionTitle { font-size: 16px; font-weight: 700; }
            #conversationCard { background: #fbfaf6; border: 1px solid #d7d2c7; border-radius: 15px; }
            #composer { background: #fbfaf6; border: 1px solid #cfc9bd; border-radius: 15px; }
            #modePill { background: #e2eee8; color: #25644f; border-radius: 9px; padding: 4px 9px; font-size: 10px; }
            QPushButton { background: #faf8f2; color: #303730; border: 1px solid #d3cec3; border-radius: 8px; padding: 7px 12px; }
            QPushButton:hover { border-color: #778f82; background: white; }
            #primaryButton { background: #1f7059; color: white; border: none; }
            #dangerButton { color: #a24639; }
            QListWidget, QLineEdit, QTextEdit, QSpinBox, QTextBrowser { background: #fbfaf6; border: 1px solid #d7d2c7; border-radius: 8px; padding: 7px; }
            QListWidget::item { padding: 8px; border-radius: 6px; }
            QListWidget::item:selected { background: #d4e8df; color: #164f40; }
            #canvas { background: #e7e3da; border: 1px solid #d3cec2; border-radius: 12px; }
            QTabWidget::pane { border: 1px solid #d3cec2; border-radius: 8px; background: #f9f7f1; }
            QTabBar::tab { padding: 7px 15px; color: #687068; }
            QTabBar::tab:selected { color: #1f7059; font-weight: 700; }
            #statusPill { background: #dce9e3; color: #28634f; border-radius: 10px; padding: 5px 11px; }
            #chat { background: #fbfaf6; color: #27302b; border: none; }
            #actionList { background: #f0ede5; color: #59635d; border: 1px solid #ded9ce; }
            #actionList::item { border-bottom: 1px solid #ded9ce; }
            #prompt { background: transparent; color: #252c28; border: none; font-size: 14px; }
            #prompt { placeholder-text-color: #657169; }
            QPushButton:checked { background: #1f7059; color: white; border-color: #1f7059; }
            #agentButton { background: #d7f05c; color: #1c251f; border: none; font-weight: 800; padding: 9px 18px; }
            QSplitter::handle { background: transparent; width: 5px; }
        """)

    def switch_view(self, index: int):
        if not hasattr(self, "view_stack"):
            return
        self.view_stack.setCurrentIndex(index)
        self.view_title.setText("与 Agent 一起制作任务书" if index == 0 else "任务书编辑器")
        for button_index, button in enumerate(self.nav_buttons[:2]):
            button.setStyleSheet(
                "background:#40564d;border-color:#6b8378;color:white;"
                if button_index == index else ""
            )

    def show_validation(self):
        self.switch_view(1)
        self.editor_tabs.setCurrentIndex(1)
        self.run_validation()

    def refresh_all(self):
        self.project_title.setText(self.store.project.title)
        selected = self.current_chapter_id
        self.chapter_list.blockSignals(True)
        self.chapter_list.clear()
        for chapter in self.store.project.chapters:
            item = QListWidgetItem(f"{chapter.title}\n{len(chapter.quests)} 个任务")
            item.setData(Qt.ItemDataRole.UserRole, chapter.id)
            self.chapter_list.addItem(item)
            if chapter.id == selected:
                self.chapter_list.setCurrentItem(item)
        self.chapter_list.blockSignals(False)
        if not self.current_chapter_id and self.store.project.chapters:
            self.current_chapter_id = self.store.project.chapters[0].id
        self.refresh_canvas()
        self.run_validation()

    def refresh_canvas(self):
        self.scene.clear()
        chapter = self.store.chapter(self.current_chapter_id)
        if chapter is None:
            self.chapter_heading.setText("选择一个章节")
            return
        self.chapter_heading.setText(chapter.title)
        nodes = {}
        for index, quest in enumerate(chapter.quests):
            row = index // 4
            offset = index % 4
            column = offset if row % 2 == 0 else 3 - offset
            x = column * 235
            y = row * 125
            task = quest.tasks[0] if quest.tasks else None
            icon_path = self.asset_index.icon_for(task.target) if self.asset_index and task else ""
            node = QuestNode(quest, x, y, icon_path)
            self.scene.addItem(node)
            nodes[quest.id] = node
        for quest in chapter.quests:
            target = nodes.get(quest.id)
            for dependency_id in quest.dependencies:
                source = nodes.get(dependency_id)
                if source is None or target is None:
                    continue
                start = source.sceneBoundingRect().center()
                end = target.sceneBoundingRect().center()
                line = QGraphicsLineItem(start.x(), start.y(), end.x(), end.y())
                line.setPen(QPen(QColor("#8a958e"), 2))
                line.setToolTip(f"{source.quest.title} -> {target.quest.title}")
                line.setZValue(-1)
                self.scene.addItem(line)
        self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-40, -40, 80, 80))

    def select_chapter(self, current, _previous):
        if current:
            self.current_chapter_id = current.data(Qt.ItemDataRole.UserRole)
            self.current_quest_id = ""
            self.switch_view(1)
            self.refresh_canvas()
            self.clear_inspector()

    def select_canvas_quest(self):
        selected = [item for item in self.scene.selectedItems() if isinstance(item, QuestNode)]
        if not selected:
            return
        quest = selected[0].quest
        if self.connect_mode:
            self._handle_connection_click(quest)
            return
        self.current_quest_id = quest.id
        self.load_inspector(quest)

    def toggle_connect_mode(self, enabled: bool):
        self.connect_mode = enabled
        self.connection_source_id = ""
        self.scene.clearSelection()
        self.connection_hint.setText("先点击前置任务 A" if enabled else "普通选择模式")

    def _handle_connection_click(self, quest):
        if not self.connection_source_id:
            self.connection_source_id = quest.id
            self.connection_hint.setText(f"前置：{quest.title}，再点击后置任务 B")
            return
        source_id = self.connection_source_id
        self.connection_source_id = ""
        if source_id == quest.id:
            self.connection_hint.setText("不能连接任务自身，请重新选择 A")
            self.scene.clearSelection()
            return
        try:
            self.store.connect(quest.id, source_id)
            self.connection_hint.setText(f"已连接 A -> {quest.title}，可继续选择下一组")
            self.append_action("connect_quests", f"{source_id} -> {quest.id}")
            self.refresh_all()
        except ValueError as exc:
            self.connection_hint.setText(str(exc))
            self.scene.clearSelection()

    def load_inspector(self, quest):
        task = quest.tasks[0] if quest.tasks else None
        self.quest_title.setText(quest.title)
        self.quest_type.setText(task.type if task else "checkmark")
        self.quest_target.setText(task.target if task else "")
        self.quest_count.setValue(task.count if task else 1)
        self.quest_description.setPlainText("\n".join(quest.description))

    def clear_inspector(self):
        self.quest_title.clear()
        self.quest_type.clear()
        self.quest_target.clear()
        self.quest_count.setValue(1)
        self.quest_description.clear()

    def save_project_title(self):
        self.store.project.title = self.project_title.text().strip() or "未命名任务书"

    def add_chapter(self):
        chapter = self.store.create_chapter(f"新章节 {len(self.store.project.chapters) + 1}")
        self.current_chapter_id = chapter.id
        self.refresh_all()

    def add_quest(self):
        if not self.current_chapter_id:
            self.add_chapter()
        quest = self.store.add_quest(self.current_chapter_id, "新任务", "", "checkmark")
        self.current_quest_id = quest.id
        self.refresh_all()

    def apply_quest_changes(self):
        if not self.current_quest_id:
            QMessageBox.information(self, "任务属性", "请先在画布中选择一个任务。")
            return
        try:
            self.store.update_quest(
                self.current_quest_id,
                title=self.quest_title.text(),
                description=self.quest_description.toPlainText(),
                task_type=self.quest_type.text(),
                target=self.quest_target.text(),
                count=self.quest_count.value(),
            )
            self.refresh_all()
        except Exception as exc:
            QMessageBox.warning(self, "无法修改", str(exc))

    def remove_quest(self):
        if self.current_quest_id and self.store.remove_quest(self.current_quest_id):
            self.current_quest_id = ""
            self.refresh_all()

    def undo(self):
        if self.store.undo():
            self.current_chapter_id = ""
            self.refresh_all()

    def redo(self):
        if self.store.redo():
            self.current_chapter_id = ""
            self.refresh_all()

    def new_project(self):
        if QMessageBox.question(self, "新建项目", "创建新项目？未保存的修改将丢失。") == QMessageBox.StandardButton.Yes:
            self.store = ProjectStore(self._starter_project())
            self.project_path = ""
            self.current_chapter_id = ""
            self.agent = None
            self.refresh_all()

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "打开 AutoFTBQ 项目", "", PROJECT_FILTER)
        if not path:
            return
        try:
            self.store = ProjectStore.load(path)
            self.project_path = path
            self.current_chapter_id = ""
            self.agent = None
            self.refresh_all()
        except Exception as exc:
            QMessageBox.critical(self, "打开失败", str(exc))

    def save_project(self):
        self.save_project_title()
        path = self.project_path
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, "保存 AutoFTBQ 项目", "questbook.autoftbq.json", PROJECT_FILTER)
        if not path:
            return
        try:
            self.store.save(path)
            self.project_path = path
            self.statusBar().showMessage(f"已保存：{path}", 5000)
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", str(exc))

    def scan_modpack(self):
        selected_folder = QFileDialog.getExistingDirectory(
            self, "选择整合包根目录或 mods 文件夹", self.store.project.mod_folder
        )
        if not selected_folder:
            return
        folder = os.path.abspath(selected_folder)
        if os.path.basename(folder).casefold() == "mods":
            folder = os.path.dirname(folder)
        mods_dir = os.path.join(folder, "mods") if os.path.isdir(os.path.join(folder, "mods")) else folder
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            items = mod_scanner.scan_folder_items(mods_dir)
            recipes = dict(getattr(mod_scanner, "_recipe_inputs_cache", {}))
            self.toolbox = QuestToolbox(items, recipes)
            self.asset_index = AssetIndex.build(
                folder,
                items,
                os.path.join(ROOT_DIR, ".autoftbq_cache", "icons"),
            )
            self.store.project.mod_folder = folder
            total = sum(len(value) for value in items.values())
            assets = self.asset_index.summary()
            self.modpack_status.setText(
                f"已读取 {len(items)} 个命名空间 / {total} 个物品\n"
                f"可预览 {assets['icons']} 个图标，另有 {assets['model_fallbacks']} 个模型待渲染"
            )
            self.agent = None
            self.append_action("scan_modpack", f"{total} items")
            self.refresh_all()
        except Exception as exc:
            QMessageBox.critical(self, "扫描失败", str(exc))
        finally:
            QApplication.restoreOverrideCursor()

    def run_validation(self):
        issues = self.store.validate(self.toolbox.all_items)
        self.validation_list.clear()
        if not issues:
            self.validation_list.addItem("通过：没有发现结构问题")
            return issues
        for issue in issues:
            prefix = "错误" if issue["severity"] == "error" else "提醒"
            self.validation_list.addItem(f"{prefix}  {issue['location']}  ·  {issue['message']}")
        return issues

    def export_snbt(self):
        issues = self.run_validation()
        errors = [issue for issue in issues if issue["severity"] == "error"]
        if errors:
            QMessageBox.warning(self, "暂不能导出", "请先处理检查结果中的错误。")
            return
        folder = QFileDialog.getExistingDirectory(self, "选择 FTB Quests 输出目录")
        if not folder:
            return
        try:
            result = import_json_to_snbt(
                json.dumps(self.store.project.to_ai_data(), ensure_ascii=False),
                mod_folder=self.store.project.mod_folder or None,
                output_dir=folder,
            )
            QMessageBox.information(self, "导出完成", f"任务书已写入：\n{result}")
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", str(exc))

    def _load_client(self):
        config_path = os.path.join(ROOT_DIR, "config.json")
        try:
            with open(config_path, "r", encoding="utf-8") as handle:
                config = json.load(handle)
        except (OSError, ValueError):
            raise RuntimeError("未找到可用配置，请先在 AutoFTBQ 1.x 中保存 API 或 Ollama 设置")
        engine = config.get("engine", "deepseek")
        provider = config.get("provider")
        api_url = config.get("api_url") if provider == "第三方自定义" else None
        client = create_chat_client(
            "ollama" if engine == "ollama" else "generic",
            api_key=config.get("api_key", ""),
            ollama_model=config.get("ollama_model"),
            provider=provider,
            api_url=api_url,
            api_model=config.get("api_model"),
        )
        self.model_label.setText(f"已连接 {provider or engine} / {getattr(client, 'model', 'default')} · 白名单工具模式")
        return client

    def send_to_agent(self):
        prompt = self.prompt.toPlainText().strip()
        if not prompt or self.agent_thread is not None:
            return
        try:
            if self.agent is None:
                self.agent = ProjectAgent(self.store, self._load_client(), self.toolbox)
        except Exception as exc:
            QMessageBox.warning(self, "Agent 未连接", str(exc))
            return
        self.append_chat("user", prompt)
        self.prompt.clear()
        self.agent_state.setText("工作中")
        self.send_button.setEnabled(False)
        self.agent_thread = AgentThread(self.agent, prompt)
        self.agent_thread.action.connect(self.append_action)
        self.agent_thread.answered.connect(self.agent_answered)
        self.agent_thread.failed.connect(self.agent_failed)
        self.agent_thread.finished.connect(self.agent_finished)
        self.agent_thread.start()

    def agent_answered(self, text):
        self.append_chat("agent", text)
        self.refresh_all()

    def agent_failed(self, text):
        self.append_chat("error", text)

    def agent_finished(self):
        self.agent_state.setText("待命")
        self.send_button.setEnabled(True)
        thread = self.agent_thread
        self.agent_thread = None
        if thread:
            thread.deleteLater()

    def append_action(self, name, detail):
        labels = {
            "get_project_summary": "读取项目",
            "list_skills": "查看内置方案",
            "load_skill": "加载内置方案",
            "create_chapter": "创建章节",
            "add_quest": "添加任务",
            "update_quest": "修改任务",
            "connect_quests": "连接任务",
            "search_items": "搜索物品",
            "get_recipe": "读取配方",
            "validate_project": "检查项目",
            "scan_modpack": "扫描整合包",
        }
        self.action_list.insertItem(0, f"{labels.get(name, name)}  {detail[:90]}")
        if name in {"create_chapter", "add_quest", "update_quest", "connect_quests"}:
            self.refresh_all()

    def append_chat(self, role, text):
        safe = escape(str(text)).replace("\n", "<br>")
        if role == "user":
            block = f"<div style='margin:12px 0 12px 45px;padding:11px;background:#26352f;color:#f3f6f4;border-radius:10px'><b>你</b><br>{safe}</div>"
        elif role == "error":
            block = f"<div style='margin:12px 35px 12px 0;padding:11px;background:#f4dfd9;color:#712f25;border-radius:10px'><b>Agent 出错</b><br>{safe}</div>"
        else:
            block = f"<div style='margin:12px 35px 12px 0;padding:11px;background:#e5eee9;color:#26322c;border-radius:10px'><b style='color:#1d7057'>Agent</b><br>{safe}</div>"
        self.chat.append(block)
        self.chat.verticalScrollBar().setValue(self.chat.verticalScrollBar().maximum())


def run_app():
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    return app.exec()
