import sys
import uuid
import threading
import time
import os
import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QLineEdit, QFormLayout,
    QSpinBox, QCheckBox, QMessageBox, QProgressBar, QLabel, QGroupBox,
    QMenuBar, QAction, QStatusBar, QComboBox, QTextEdit, QFileDialog,
    QHeaderView, QStyleFactory, QSystemTrayIcon, QMenu, QScrollArea,
    QListWidget, QAbstractItemView
)
from PyQt5.QtCore import Qt, QTimer, QEvent, pyqtSignal, pyqtSlot, QObject
from PyQt5.QtGui import QIcon, QPalette, QColor, QBrush
from config_manager import ConfigManager, ServerConfig
from ssh_sync import SSHSync
from auto_start import AutoStartManager
from time_sync import TimeSync
from utils.logger import log_message, log_info, log_error, log_debug
from gui.log_level_dialog import LogLevelDialog

class TimeSyncSignals(QObject):
    sync_result = pyqtSignal(bool, str, object)

class StatusUpdateSignals(QObject):
    status_updated = pyqtSignal(int, str, QColor, str)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Linux目录同步工具")
        self.setGeometry(100, 100, 1000, 600)
        
        self.setWindowIcon(self.get_app_icon())
        
        self.config_manager = ConfigManager()
        self.auto_start_manager = AutoStartManager()
        self.time_sync = TimeSync()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_scheduled_sync)
        
        # 在线状态检测定时器（每5秒检测一次）
        self.online_timer = QTimer(self)
        self.online_timer.timeout.connect(self.check_online_status)
        
        # 校时信号
        self.time_sync_signals = TimeSyncSignals()
        self.time_sync_signals.sync_result.connect(self.on_time_sync_result)
        
        # 在线状态更新信号
        self.status_signals = StatusUpdateSignals()
        self.status_signals.status_updated.connect(self.update_status_item)
        
        self.init_ui()
        self.load_server_list()
        self.timer.start(1000)  # 每秒检查一次，确保不会错过同步时间
        self.online_timer.start(5000)  # 每5秒检测一次在线状态
        
        self.check_online_status()
        
        self.init_tray_icon()
    
    def on_time_sync_result(self, success, msg, progress_dialog):
        """处理校时结果（在主线程中执行）"""
        progress_dialog.hide()
        if success:
            QMessageBox.information(self, "校时成功", msg)
        else:
            QMessageBox.warning(self, "校时失败", msg)

    def update_status_item(self, row, text, color, tooltip):
        """更新状态表格项（在主线程中执行）"""
        status_item = QTableWidgetItem(text)
        status_item.setForeground(QBrush(color))
        status_item.setTextAlignment(Qt.AlignCenter)
        status_item.setToolTip(tooltip)
        self.table.setItem(row, 6, status_item)

    def get_app_icon(self):
        icon_path = os.path.join(os.path.dirname(__file__), '..', 'logo.ico')
        if os.path.exists(icon_path):
            return QIcon(icon_path)
        return QIcon()

    def init_ui(self):
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint | Qt.WindowSystemMenuHint)
        self.setStyle(QStyleFactory.create('Fusion'))
        
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(240, 240, 245))
        palette.setColor(QPalette.WindowText, QColor(40, 40, 45))
        palette.setColor(QPalette.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.AlternateBase, QColor(245, 245, 250))
        palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
        palette.setColor(QPalette.ToolTipText, QColor(40, 40, 45))
        palette.setColor(QPalette.Text, QColor(40, 40, 45))
        palette.setColor(QPalette.Button, QColor(245, 245, 250))
        palette.setColor(QPalette.ButtonText, QColor(40, 40, 45))
        palette.setColor(QPalette.Highlight, QColor(51, 102, 204))
        palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        self.setPalette(palette)

        menubar = self.menuBar()
        settings_menu = menubar.addMenu("设置")
        
        self.auto_start_action = QAction("开机自启动", self, checkable=True)
        self.auto_start_enabled, _ = self.auto_start_manager.is_auto_start_enabled()
        self.auto_start_action.setChecked(self.auto_start_enabled)
        self.auto_start_action.triggered.connect(self.toggle_auto_start)
        settings_menu.addAction(self.auto_start_action)
        
        settings_menu.addSeparator()
        
        log_level_action = QAction("日志级别设置", self)
        log_level_action.triggered.connect(self.show_log_level_dialog)
        settings_menu.addAction(log_level_action)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)

        toolbar_widget = QWidget()
        toolbar_layout = QHBoxLayout(toolbar_widget)
        toolbar_layout.setSpacing(10)
        
        self.add_btn = QPushButton("添加任务")
        self.add_btn.setStyleSheet(self.get_button_style())
        self.add_btn.clicked.connect(self.show_add_dialog)
        
        self.edit_btn = QPushButton("编辑任务")
        self.edit_btn.setStyleSheet(self.get_button_style())
        self.edit_btn.clicked.connect(self.show_edit_dialog)
        
        self.delete_btn = QPushButton("删除任务")
        self.delete_btn.setStyleSheet(self.get_danger_button_style())
        self.delete_btn.clicked.connect(self.delete_server)
        
        self.sync_btn = QPushButton("立即同步")
        self.sync_btn.setStyleSheet(self.get_success_button_style())
        self.sync_btn.clicked.connect(self.sync_selected)
        
        self.sync_all_btn = QPushButton("同步全部")
        self.sync_all_btn.setStyleSheet(self.get_button_style())
        self.sync_all_btn.clicked.connect(self.sync_all)
        
        self.time_sync_btn = QPushButton("校时")
        self.time_sync_btn.setStyleSheet(self.get_button_style())
        self.time_sync_btn.clicked.connect(self.do_time_sync)
        
        self.refresh_status_btn = QPushButton("刷新在线状态")
        self.refresh_status_btn.setStyleSheet(self.get_button_style())
        self.refresh_status_btn.clicked.connect(lambda: self.check_online_status(True))
        
        toolbar_layout.addWidget(self.add_btn)
        toolbar_layout.addWidget(self.edit_btn)
        toolbar_layout.addWidget(self.delete_btn)
        toolbar_layout.addWidget(self.sync_btn)
        toolbar_layout.addWidget(self.sync_all_btn)
        toolbar_layout.addWidget(self.refresh_status_btn)
        toolbar_layout.addWidget(self.time_sync_btn)
        
        toolbar_widget.setStyleSheet("QWidget { background-color: white; border-radius: 8px; padding: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }")
        layout.addWidget(toolbar_widget)

        table_widget = QWidget()
        table_widget.setStyleSheet("QWidget { background-color: white; border-radius: 8px; padding: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }")
        table_layout = QVBoxLayout(table_widget)
        
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["选择", "任务名称", "服务器地址", "远程目录", "本地目录", "自动同步", "状态"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectItems)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QTableWidget.MultiSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setColumnWidth(0, 50)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Interactive)
        header.setSectionResizeMode(6, QHeaderView.Fixed)
        
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 140)
        self.table.setColumnWidth(5, 90)
        self.table.setColumnWidth(6, 80)
        
        header.setStyleSheet("""
            QHeaderView {
                border: none;
                margin: 0;
                padding: 0;
                selection-background-color: transparent;
            }
            QHeaderView::section {
                background-color: #3b82f6;
                color: white;
                padding: 12px 8px;
                border-bottom: 1px solid #2563eb;
                font-weight: 600;
                font-size: 13px;
                min-height: 36px;
                border-left: 1px solid #2563eb;
                border-right: none;
                selection-background-color: transparent;
            }
            QHeaderView::section:first {
                border-left: none;
            }
            QHeaderView::section:hover {
                background-color: #3b82f6;
            }
            QHeaderView::section:selected {
                background-color: #3b82f6;
            }
            QHeaderView::section:pressed {
                background-color: #3b82f6;
            }
            QHeaderView::section:disabled {
                background-color: #6b7280;
            }
        """)
        header.setFocusPolicy(Qt.NoFocus)
        header.setEnabled(False)
        header.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        header.setSectionsClickable(False)
        header.installEventFilter(self)
        
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setStyleSheet("""
            QTableWidget { 
                border: none; 
                gridline-color: #e9ecef; 
                margin: 0;
                padding: 0;
                border-left: 1px solid #dee2e6;
                border-right: 1px solid #dee2e6;
                border-bottom: 1px solid #dee2e6;
                background-color: white;
                pointer-events: none;
                selection-background-color: transparent;
                selection-color: inherit;
            }
            QTableWidget::item { 
                padding: 8px; 
                border-bottom: 1px solid #f0f0f0; 
                margin: 0;
                border-left: 1px solid #dee2e6;
                background-color: white;
                pointer-events: none;
            }
            QTableWidget::item:first {
                border-left: none;
            }
            QTableWidget::item:selected,
            QTableWidget::item:hover { 
                background-color: white; 
            }
            QTableWidget::row:alternate {
                background-color: #f8f9fa;
            }
        """)
        
        table_layout.addWidget(self.table)
        layout.addWidget(table_widget)
        
        # 同步记录区域
        self.sync_log_widget = QWidget()
        self.sync_log_widget.setStyleSheet("QWidget { background-color: white; border-radius: 8px; padding: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }")
        self.sync_log_widget.setFixedHeight(150)
        sync_log_layout = QVBoxLayout(self.sync_log_widget)
        sync_log_layout.setContentsMargins(0, 0, 0, 0)
        sync_log_layout.setSpacing(0)
        
        self.sync_log_text = QTextEdit()
        self.sync_log_text.setReadOnly(True)
        self.sync_log_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e9ecef;
                border-radius: 4px;
                padding: 6px;
                font-family: Consolas, monospace;
                font-size: 11px;
                background-color: #f8f9fa;
                color: #495057;
            }
        """)
        sync_log_layout.addWidget(self.sync_log_text)
        
        layout.addWidget(self.sync_log_widget)
        
        self.selected_rows = []
        self.sync_logs = []
        self.startup_time = time.time()

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")
        self.status_bar.setStyleSheet("QStatusBar { background-color: #f8f9fa; padding: 6px; }")
    
    @pyqtSlot(str, bool, str)
    def add_sync_log(self, task_name, success, message):
        """添加同步日志记录"""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "成功" if success else "失败"
        log_entry = f"[{now}] {task_name} - {status}: {message}"
        
        self.sync_logs.insert(0, log_entry)
        if len(self.sync_logs) > 50:
            self.sync_logs.pop()
        
        self.sync_log_text.setPlainText("\n".join(self.sync_logs))
        self.sync_log_text.verticalScrollBar().setValue(0)
        
        self.log_to_file(f"同步记录: {log_entry}")
    
    def log_to_file(self, message):
        """记录操作日志到用户文件夹"""
        log_message("MainWindow", "INFO", message)

    def init_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.get_app_icon())
        
        tray_menu = QMenu()
        
        show_action = QAction("显示窗口", self)
        show_action.triggered.connect(self.show_window)
        tray_menu.addAction(show_action)
        
        quit_action = QAction("退出程序", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_window()

    def show_window(self):
        self.show()
        self.setWindowState(Qt.WindowActive)

    def quit_application(self):
        self.tray_icon.hide()
        sys.exit(0)

    def closeEvent(self, event):
        dialog = QMessageBox(self)
        dialog.setWindowTitle("关闭程序")
        dialog.setText("请选择操作：")
        dialog.setIcon(QMessageBox.Question)
        
        minimize_btn = dialog.addButton("最小化到托盘", QMessageBox.ActionRole)
        close_btn = dialog.addButton("关闭此应用程序", QMessageBox.ActionRole)
        
        dialog.exec_()
        
        if dialog.clickedButton() == close_btn:
            self.tray_icon.hide()
            QApplication.quit()
            event.accept()
        else:
            self.hide()
            event.ignore()

    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange:
            if self.windowState() & Qt.WindowMinimized:
                self.hide()
                self.setWindowState(Qt.WindowNoState)
                event.ignore()
        super().changeEvent(event)

    def eventFilter(self, obj, event):
        header = self.table.horizontalHeader()
        if obj == header:
            if event.type() == QEvent.MouseButtonPress or \
               event.type() == QEvent.MouseButtonRelease or \
               event.type() == QEvent.MouseButtonDblClick or \
               event.type() == QEvent.MouseMove or \
               event.type() == QEvent.HoverEnter or \
               event.type() == QEvent.HoverLeave or \
               event.type() == QEvent.HoverMove:
                return True
        return super().eventFilter(obj, event)

    def get_button_style(self):
        return """
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #60a5fa;
            }
            QPushButton:pressed {
                background-color: #2563eb;
            }
        """

    def get_success_button_style(self):
        return """
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #34d399;
            }
            QPushButton:pressed {
                background-color: #059669;
            }
        """

    def get_danger_button_style(self):
        return """
            QPushButton {
                background-color: #ef4444;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #f87171;
            }
            QPushButton:pressed {
                background-color: #dc2626;
            }
        """

    def toggle_auto_start(self, checked):
        success, msg = self.auto_start_manager.set_auto_start(checked)
        if success:
            self.auto_start_enabled = checked
            QMessageBox.information(self, "提示", msg)
        else:
            self.auto_start_action.setChecked(not checked)
            QMessageBox.warning(self, "错误", msg)

    def show_log_level_dialog(self):
        """显示日志级别设置对话框"""
        dialog = LogLevelDialog(self)
        dialog.exec_()

    def do_time_sync(self):
        """执行校时操作"""
        progress_dialog = QMessageBox(self)
        progress_dialog.setWindowTitle("校时")
        progress_dialog.setText("正在连接time.windows.com进行校时...")
        progress_dialog.setStandardButtons(QMessageBox.NoButton)
        progress_dialog.show()
        
        def sync_worker():
            try:
                success, msg = self.time_sync.sync_with_backup()
            except Exception as e:
                success = False
                msg = f"校时过程中发生错误: {str(e)}"
            
            # 使用信号在主线程中显示结果
            self.time_sync_signals.sync_result.emit(success, msg, progress_dialog)
        
        thread = threading.Thread(target=sync_worker)
        thread.daemon = True
        thread.start()

    def load_server_list(self):
        self.table.setRowCount(0)
        for config in self.config_manager.get_all_configs():
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            check_item.setCheckState(Qt.Unchecked)
            check_item.setToolTip("勾选以选择此任务")
            check_item.setData(Qt.UserRole, 'checkbox')
            self.table.setItem(row, 0, check_item)
            
            name_item = QTableWidgetItem(config.name)
            name_item.setToolTip(config.name)
            self.table.setItem(row, 1, name_item)
            
            address = f"{config.hostname}:{config.port}"
            addr_item = QTableWidgetItem(address)
            addr_item.setToolTip(address)
            self.table.setItem(row, 2, addr_item)
            
            remote_item = QTableWidgetItem(config.remote_dir)
            remote_item.setToolTip(config.remote_dir)
            self.table.setItem(row, 3, remote_item)
            
            local_item = QTableWidgetItem(config.local_dir)
            local_item.setToolTip(config.local_dir)
            self.table.setItem(row, 4, local_item)
            
            # 显示同步计划信息
            sync_type = getattr(config, 'sync_type', 'interval')
            if config.enabled:
                if sync_type == 'interval':
                    sync_interval = getattr(config, 'sync_interval', 0)
                    if sync_interval > 0:
                        sync_text = f"间隔{sync_interval}分钟"
                        sync_tooltip = f"每隔{sync_interval}分钟自动同步"
                    else:
                        sync_text = "关闭"
                        sync_tooltip = "未设置自动同步"
                elif sync_type == 'monthly':
                    monthly_days = getattr(config, 'monthly_days', [])
                    monthly_times = getattr(config, 'monthly_times', ['00:00'])
                    days_str = ','.join(map(str, monthly_days)) if monthly_days else '无'
                    times_str = ','.join(monthly_times)
                    sync_text = f"每月{days_str}日 {times_str}"
                    sync_tooltip = f"每月{days_str}日的{times_str}自动同步"
                elif sync_type == 'weekly':
                    weekly_days = getattr(config, 'weekly_days', [])
                    weekly_times = getattr(config, 'weekly_times', ['00:00'])
                    week_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                    days_str = ','.join([week_names[i] for i in weekly_days]) if weekly_days else '无'
                    times_str = ','.join(weekly_times)
                    sync_text = f"每{days_str} {times_str}"
                    sync_tooltip = f"每{days_str}的{times_str}自动同步"
                elif sync_type == 'daily':
                    daily_times = getattr(config, 'daily_times', ['00:00'])
                    times_str = ','.join(daily_times)
                    sync_text = f"每天{times_str}"
                    sync_tooltip = f"每天{times_str}自动同步"
                else:
                    sync_text = "关闭"
                    sync_tooltip = "未设置自动同步"
            else:
                sync_text = "关闭"
                sync_tooltip = "未启用定时同步"
            
            sync_item = QTableWidgetItem(sync_text)
            sync_item.setToolTip(sync_tooltip)
            self.table.setItem(row, 5, sync_item)
            
            status_item = QTableWidgetItem("未检测")
            status_item.setForeground(QBrush(QColor(100, 100, 100)))
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setToolTip("在线状态未检测")
            self.table.setItem(row, 6, status_item)

    def check_online_status(self, show_progress=False):
        """检测所有服务器在线状态"""
        configs = self.config_manager.get_all_configs()
        
        for i, config in enumerate(configs):
            current_item = self.table.item(i, 6)
            current_status = current_item.text() if current_item else "未检测"
            
            if not show_progress and current_status == "在线":
                continue
            
            if show_progress:
                status_item = QTableWidgetItem("检测中...")
                status_item.setForeground(QBrush(QColor(234, 179, 8)))
                status_item.setTextAlignment(Qt.AlignCenter)
                status_item.setToolTip("正在检测在线状态...")
                self.table.setItem(i, 6, status_item)
            
            def check_status(index, cfg):
                try:
                    ssh = SSHSync(cfg.hostname, cfg.port, cfg.username, cfg.password)
                    success, msg = ssh.check_connection()
                except Exception as e:
                    success = False
                
                if success:
                    color = QColor(40, 167, 69)
                    status_text = "在线"
                    tooltip = f"{cfg.hostname}:{cfg.port} - 在线"
                else:
                    color = QColor(220, 53, 69)
                    status_text = "离线"
                    tooltip = f"{cfg.hostname}:{cfg.port} - 离线"
                
                self.status_signals.status_updated.emit(index, status_text, color, tooltip)
            
            thread = threading.Thread(target=check_status, args=(i, config))
            thread.daemon = True
            thread.start()

    def show_add_dialog(self):
        self.log_to_file("打开添加任务对话框")
        dialog = ServerConfigDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            config = dialog.get_config()
            config.id = str(uuid.uuid4())
            success, msg = self.config_manager.add_config(config)
            if success:
                QMessageBox.information(self, "成功", "任务配置已添加")
                self.load_server_list()
                self.check_online_status()
                self.log_to_file(f"任务添加成功: {config.name}")
            else:
                QMessageBox.warning(self, "错误", msg)
                self.log_to_file(f"任务添加失败: {msg}")
        else:
            self.log_to_file("取消添加任务")

    def show_edit_dialog(self):
        self.log_to_file("打开编辑任务对话框")
        checked_rows = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                checked_rows.append(row)
        
        if len(checked_rows) != 1:
            QMessageBox.warning(self, "提示", "请勾选且仅勾选一个任务进行编辑")
            return
        
        row = checked_rows[0]
        config_id = self.get_config_id_by_row(row)
        if not config_id:
            return
        
        config = self.config_manager.get_config(config_id)
        if not config:
            return
        
        dialog = ServerConfigDialog(self, config)
        if dialog.exec_() == QDialog.Accepted:
            updated_config = dialog.get_config()
            updated_config.id = config_id
            success, msg = self.config_manager.update_config(config_id, updated_config)
            if success:
                QMessageBox.information(self, "成功", "任务配置已更新")
                self.load_server_list()
                self.check_online_status()
                self.log_to_file(f"任务编辑成功: {updated_config.name}")
            else:
                QMessageBox.warning(self, "错误", msg)
                self.log_to_file(f"任务编辑失败: {msg}")
        else:
            self.log_to_file("取消编辑任务")

    def get_config_id_by_row(self, row):
        configs = self.config_manager.get_all_configs()
        if row < len(configs):
            return configs[row].id
        return None

    def delete_server(self):
        self.log_to_file("删除任务操作")
        checked_rows = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                checked_rows.append(row)
        
        if not checked_rows:
            QMessageBox.warning(self, "提示", "请勾选要删除的任务")
            return
        
        reply = QMessageBox.question(self, "确认删除", f"确定要删除选中的 {len(checked_rows)} 个任务配置吗？",
                                    QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            config_ids = []
            for row in checked_rows:
                config_id = self.get_config_id_by_row(row)
                if config_id:
                    config_ids.append(config_id)
            
            deleted_count = 0
            for config_id in config_ids:
                success, _ = self.config_manager.delete_config(config_id)
                if success:
                    deleted_count += 1
            
            QMessageBox.information(self, "成功", f"已删除 {deleted_count} 个任务配置")
            self.load_server_list()
            self.log_to_file(f"删除任务成功，共删除 {deleted_count} 个")
        else:
            self.log_to_file("取消删除任务")

    def sync_selected(self):
        checked_rows = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                checked_rows.append(row)
        
        if not checked_rows:
            QMessageBox.warning(self, "提示", "请先勾选要同步的任务")
            return
        
        config_ids = [self.get_config_id_by_row(row) for row in checked_rows]
        config_ids = [cid for cid in config_ids if cid]
        
        if not config_ids:
            return
        
        for config_id in config_ids:
            config = self.config_manager.get_config(config_id)
            if config:
                self.start_sync(config)

    def sync_all(self):
        configs = self.config_manager.get_all_configs()
        
        if not configs:
            QMessageBox.warning(self, "提示", "没有添加任何任务")
            return
        
        for config in configs:
            self.start_sync(config)

    def start_sync(self, config, is_scheduled=False):
        self.log_to_file(f"start_sync called for {config.name}, is_scheduled={is_scheduled}, window visible={self.isVisible()}")
        progress_dialog = ProgressDialog(self, config, is_scheduled)
        if is_scheduled:
            progress_dialog.show()
            self.log_to_file(f"ProgressDialog shown for scheduled sync")
        else:
            progress_dialog.exec_()
            self.log_to_file(f"ProgressDialog exec completed")

    def check_scheduled_sync(self):
        configs = self.config_manager.get_all_configs()
        now = datetime.datetime.now()
        current_day = now.day
        current_weekday = now.weekday()  # 0=周一, 6=周日
        current_time_str = f"{now.hour:02d}:{now.minute:02d}"

        for config in configs:
            if not config.enabled:
                continue

            sync_type = getattr(config, 'sync_type', 'interval')
            should_sync = False

            if sync_type == 'interval':
                sync_interval = getattr(config, 'sync_interval', 0)
                if sync_interval > 0:
                    last_sync = getattr(config, 'last_sync', 0)
                    if time.time() - last_sync > sync_interval * 60:
                        should_sync = True

            elif sync_type == 'monthly':
                monthly_days = getattr(config, 'monthly_days', [])
                monthly_times = getattr(config, 'monthly_times', ['00:00'])
                if current_day in monthly_days and current_time_str in monthly_times:
                    # 用"日期+时间"作为去重键，确保同一个时间点每天只触发一次
                    sync_key = f"monthly_{current_day}_{current_time_str}"
                    last_sync = getattr(config, 'last_sync', 0)
                    last_key = getattr(config, '_last_sync_key', '')
                    if sync_key != last_key:
                        should_sync = True
                        config._last_sync_key = sync_key

            elif sync_type == 'weekly':
                weekly_days = getattr(config, 'weekly_days', [])
                weekly_times = getattr(config, 'weekly_times', ['00:00'])
                if current_weekday in weekly_days and current_time_str in weekly_times:
                    sync_key = f"weekly_{current_weekday}_{current_time_str}"
                    last_sync = getattr(config, 'last_sync', 0)
                    last_key = getattr(config, '_last_sync_key', '')
                    if sync_key != last_key:
                        should_sync = True
                        config._last_sync_key = sync_key

            elif sync_type == 'daily':
                daily_times = getattr(config, 'daily_times', ['00:00'])
                if current_time_str in daily_times:
                    sync_key = f"daily_{current_time_str}"
                    last_sync = getattr(config, 'last_sync', 0)
                    last_key = getattr(config, '_last_sync_key', '')
                    if sync_key != last_key:
                        should_sync = True
                        config._last_sync_key = sync_key

            if should_sync:
                config.last_sync = time.time()
                self.config_manager.update_last_sync(config.id, config.last_sync)
                self.log_to_file(f"定时同步触发: {config.name}")
                self.start_sync(config, is_scheduled=True)

class ServerConfigDialog(QDialog):
    def get_input_style(self):
        return """
            QLineEdit, QSpinBox, QComboBox {
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 13px;
                background-color: white;
            }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border-color: #80bdff;
                outline: none;
                box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.25);
            }
        """

    def __init__(self, parent, config=None):
        super().__init__(parent)
        self.setWindowTitle("任务配置" if config else "添加任务")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.setWindowIcon(parent.windowIcon())
        self.setModal(True)

        self.setStyle(QStyleFactory.create('Fusion'))
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(240, 240, 245))
        self.setPalette(palette)

        self.config = config
        self.monthly_day_checks = []
        self.weekly_day_checks = []

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        form_group = QGroupBox()
        form_group.setStyleSheet("QGroupBox { border: 1px solid #e9ecef; border-radius: 8px; padding: 15px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px 0 5px; background-color: #f8f9fa; }")

        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        self.name_edit = QLineEdit()
        self.name_edit.setStyleSheet(self.get_input_style())
        self.hostname_edit = QLineEdit()
        self.hostname_edit.setStyleSheet(self.get_input_style())

        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(22)
        self.port_spin.setButtonSymbols(QSpinBox.NoButtons)
        self.port_spin.setStyleSheet("""
            QSpinBox {
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 14px;
                background-color: white;
            }
            QSpinBox:focus {
                border-color: #3b82f6;
                outline: none;
            }
        """)

        self.username_edit = QLineEdit()
        self.username_edit.setStyleSheet(self.get_input_style())

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setStyleSheet(self.get_input_style())

        self.root_password_edit = QLineEdit()
        self.root_password_edit.setEchoMode(QLineEdit.Password)
        self.root_password_edit.setStyleSheet(self.get_input_style())

        self.remote_dir_edit = QLineEdit()
        self.remote_dir_edit.setStyleSheet(self.get_input_style())

        local_dir_layout = QHBoxLayout()
        self.local_dir_edit = QLineEdit()
        self.local_dir_edit.setStyleSheet(self.get_input_style())
        self.local_browse_btn = QPushButton("浏览")
        self.local_browse_btn.setStyleSheet("QPushButton { background-color: #5a6268; color: white; border: none; padding: 6px 12px; border-radius: 4px; font-size: 12px; } QPushButton:hover { background-color: #6c757d; }")
        self.local_browse_btn.clicked.connect(self.browse_local_dir)
        local_dir_layout.addWidget(self.local_dir_edit)
        local_dir_layout.addWidget(self.local_browse_btn)

        self.enabled_check = QCheckBox("启用定时同步")
        self.enabled_check.stateChanged.connect(self.toggle_sync_settings)

        # 同步类型选择
        sync_type_layout = QHBoxLayout()
        self.sync_type_combo = QComboBox()
        self.sync_type_combo.addItems(["时间间隔", "月计划", "周计划", "日计划"])
        self.sync_type_combo.setStyleSheet(self.get_input_style())
        self.sync_type_combo.currentIndexChanged.connect(self.change_sync_type)
        sync_type_layout.addWidget(self.sync_type_combo)

        # 时间间隔设置
        self.interval_widget = QWidget()
        interval_layout = QHBoxLayout(self.interval_widget)
        interval_layout.setContentsMargins(0, 0, 0, 0)
        self.sync_interval_spin = QSpinBox()
        self.sync_interval_spin.setRange(1, 1440)
        self.sync_interval_spin.setValue(60)
        self.sync_interval_spin.setStyleSheet(self.get_input_style())
        interval_layout.addWidget(self.sync_interval_spin)
        interval_layout.addWidget(QLabel("分钟"))

        # 月计划设置
        self.monthly_widget = QWidget()
        monthly_layout = QVBoxLayout(self.monthly_widget)
        monthly_layout.setContentsMargins(0, 0, 0, 0)

        monthly_days_label = QLabel("选择日期 (1-31日):")
        monthly_days_layout = QGridLayout()
        for day in range(1, 32):
            check = QCheckBox(str(day))
            check.setStyleSheet("QCheckBox { font-size: 12px; padding: 2px 6px; }")
            self.monthly_day_checks.append(check)
            row = (day - 1) // 7
            col = (day - 1) % 7
            monthly_days_layout.addWidget(check, row, col)
        monthly_layout.addWidget(monthly_days_label)
        monthly_layout.addLayout(monthly_days_layout)

        # 月计划时间列表
        monthly_time_label = QLabel("同步时间（可添加多个）:")
        self.monthly_time_list = QListWidget()
        self.monthly_time_list.setMaximumHeight(80)
        self.monthly_time_list.setSelectionMode(QAbstractItemView.SingleSelection)
        monthly_time_btn_layout = QHBoxLayout()
        self.monthly_hour_spin = QSpinBox()
        self.monthly_hour_spin.setRange(0, 23)
        self.monthly_hour_spin.setValue(0)
        self.monthly_hour_spin.setStyleSheet(self.get_input_style())
        monthly_time_btn_layout.addWidget(self.monthly_hour_spin)
        monthly_time_btn_layout.addWidget(QLabel("时"))
        self.monthly_minute_spin = QSpinBox()
        self.monthly_minute_spin.setRange(0, 59)
        self.monthly_minute_spin.setValue(0)
        self.monthly_minute_spin.setStyleSheet(self.get_input_style())
        monthly_time_btn_layout.addWidget(self.monthly_minute_spin)
        monthly_time_btn_layout.addWidget(QLabel("分"))
        monthly_add_btn = QPushButton("添加")
        monthly_add_btn.setStyleSheet("QPushButton { background-color: #28a745; color: white; border: none; padding: 4px 12px; border-radius: 4px; font-size: 12px; } QPushButton:hover { background-color: #218838; }")
        monthly_add_btn.clicked.connect(lambda: self._add_time_to_list(self.monthly_time_list, self.monthly_hour_spin, self.monthly_minute_spin))
        monthly_time_btn_layout.addWidget(monthly_add_btn)
        monthly_remove_btn = QPushButton("删除")
        monthly_remove_btn.setStyleSheet("QPushButton { background-color: #dc3545; color: white; border: none; padding: 4px 12px; border-radius: 4px; font-size: 12px; } QPushButton:hover { background-color: #c82333; }")
        monthly_remove_btn.clicked.connect(lambda: self._remove_selected_time(self.monthly_time_list))
        monthly_time_btn_layout.addWidget(monthly_remove_btn)
        monthly_layout.addWidget(monthly_time_label)
        monthly_layout.addWidget(self.monthly_time_list)
        monthly_layout.addLayout(monthly_time_btn_layout)

        self.monthly_warning_label = QLabel("")
        self.monthly_warning_label.setStyleSheet("QLabel { color: #dc3545; font-size: 11px; }")
        monthly_layout.addWidget(self.monthly_warning_label)

        # 周计划设置
        self.weekly_widget = QWidget()
        weekly_layout = QVBoxLayout(self.weekly_widget)
        weekly_layout.setContentsMargins(0, 0, 0, 0)

        weekly_days_label = QLabel("选择星期:")
        weekly_days_layout = QHBoxLayout()
        week_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        for i, name in enumerate(week_names):
            check = QCheckBox(name)
            check.setStyleSheet("QCheckBox { font-size: 11px; }")
            self.weekly_day_checks.append(check)
            weekly_days_layout.addWidget(check)
        weekly_layout.addWidget(weekly_days_label)
        weekly_layout.addLayout(weekly_days_layout)

        # 周计划时间列表
        weekly_time_label = QLabel("同步时间（可添加多个）:")
        self.weekly_time_list = QListWidget()
        self.weekly_time_list.setMaximumHeight(80)
        self.weekly_time_list.setSelectionMode(QAbstractItemView.SingleSelection)
        weekly_time_btn_layout = QHBoxLayout()
        self.weekly_hour_spin = QSpinBox()
        self.weekly_hour_spin.setRange(0, 23)
        self.weekly_hour_spin.setValue(0)
        self.weekly_hour_spin.setStyleSheet(self.get_input_style())
        weekly_time_btn_layout.addWidget(self.weekly_hour_spin)
        weekly_time_btn_layout.addWidget(QLabel("时"))
        self.weekly_minute_spin = QSpinBox()
        self.weekly_minute_spin.setRange(0, 59)
        self.weekly_minute_spin.setValue(0)
        self.weekly_minute_spin.setStyleSheet(self.get_input_style())
        weekly_time_btn_layout.addWidget(self.weekly_minute_spin)
        weekly_time_btn_layout.addWidget(QLabel("分"))
        weekly_add_btn = QPushButton("添加")
        weekly_add_btn.setStyleSheet("QPushButton { background-color: #28a745; color: white; border: none; padding: 4px 12px; border-radius: 4px; font-size: 12px; } QPushButton:hover { background-color: #218838; }")
        weekly_add_btn.clicked.connect(lambda: self._add_time_to_list(self.weekly_time_list, self.weekly_hour_spin, self.weekly_minute_spin))
        weekly_time_btn_layout.addWidget(weekly_add_btn)
        weekly_remove_btn = QPushButton("删除")
        weekly_remove_btn.setStyleSheet("QPushButton { background-color: #dc3545; color: white; border: none; padding: 4px 12px; border-radius: 4px; font-size: 12px; } QPushButton:hover { background-color: #c82333; }")
        weekly_remove_btn.clicked.connect(lambda: self._remove_selected_time(self.weekly_time_list))
        weekly_time_btn_layout.addWidget(weekly_remove_btn)
        weekly_layout.addWidget(weekly_time_label)
        weekly_layout.addWidget(self.weekly_time_list)
        weekly_layout.addLayout(weekly_time_btn_layout)

        # 日计划设置
        self.daily_widget = QWidget()
        daily_layout = QVBoxLayout(self.daily_widget)
        daily_layout.setContentsMargins(0, 0, 0, 0)
        daily_time_label = QLabel("同步时间（可添加多个）:")
        self.daily_time_list = QListWidget()
        self.daily_time_list.setMaximumHeight(80)
        self.daily_time_list.setSelectionMode(QAbstractItemView.SingleSelection)
        daily_time_btn_layout = QHBoxLayout()
        self.daily_hour_spin = QSpinBox()
        self.daily_hour_spin.setRange(0, 23)
        self.daily_hour_spin.setValue(0)
        self.daily_hour_spin.setStyleSheet(self.get_input_style())
        daily_time_btn_layout.addWidget(self.daily_hour_spin)
        daily_time_btn_layout.addWidget(QLabel("时"))
        self.daily_minute_spin = QSpinBox()
        self.daily_minute_spin.setRange(0, 59)
        self.daily_minute_spin.setValue(0)
        self.daily_minute_spin.setStyleSheet(self.get_input_style())
        daily_time_btn_layout.addWidget(self.daily_minute_spin)
        daily_time_btn_layout.addWidget(QLabel("分"))
        daily_add_btn = QPushButton("添加")
        daily_add_btn.setStyleSheet("QPushButton { background-color: #28a745; color: white; border: none; padding: 4px 12px; border-radius: 4px; font-size: 12px; } QPushButton:hover { background-color: #218838; }")
        daily_add_btn.clicked.connect(lambda: self._add_time_to_list(self.daily_time_list, self.daily_hour_spin, self.daily_minute_spin))
        daily_time_btn_layout.addWidget(daily_add_btn)
        daily_remove_btn = QPushButton("删除")
        daily_remove_btn.setStyleSheet("QPushButton { background-color: #dc3545; color: white; border: none; padding: 4px 12px; border-radius: 4px; font-size: 12px; } QPushButton:hover { background-color: #c82333; }")
        daily_remove_btn.clicked.connect(lambda: self._remove_selected_time(self.daily_time_list))
        daily_time_btn_layout.addWidget(daily_remove_btn)
        daily_layout.addWidget(daily_time_label)
        daily_layout.addWidget(self.daily_time_list)
        daily_layout.addLayout(daily_time_btn_layout)

        form_layout.addRow("任务名称:", self.name_edit)
        form_layout.addRow("服务器地址:", self.hostname_edit)
        form_layout.addRow("SSH端口:", self.port_spin)
        form_layout.addRow("用户名:", self.username_edit)
        form_layout.addRow("密码:", self.password_edit)
        form_layout.addRow("Root密码:", self.root_password_edit)
        form_layout.addRow("远程目录:", self.remote_dir_edit)
        form_layout.addRow("本地目录:", local_dir_layout)
        form_layout.addRow(self.enabled_check)
        form_layout.addRow("同步类型:", sync_type_layout)
        form_layout.addRow("同步设置:", self.interval_widget)
        form_layout.addRow("", self.monthly_widget)
        form_layout.addRow("", self.weekly_widget)
        form_layout.addRow("", self.daily_widget)

        form_group.setLayout(form_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_group)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: #f0f0f5; }")
        layout.addWidget(scroll)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.ok_btn = QPushButton("确定")
        self.ok_btn.setStyleSheet("QPushButton { background-color: #007bff; color: white; border: none; padding: 10px 24px; border-radius: 6px; font-size: 14px; font-weight: 500; } QPushButton:hover { background-color: #0069d9; }")
        self.ok_btn.clicked.connect(self.validate_and_accept)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setStyleSheet("QPushButton { background-color: #6c757d; color: white; border: none; padding: 10px 24px; border-radius: 6px; font-size: 14px; font-weight: 500; } QPushButton:hover { background-color: #5a6268; }")
        self.cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

        # 初始化隐藏其他计划设置
        self.monthly_widget.hide()
        self.weekly_widget.hide()
        self.daily_widget.hide()

        # 连接月计划日期变化信号
        for check in self.monthly_day_checks:
            check.stateChanged.connect(self.check_monthly_days_warning)

        if config:
            self.load_config()

        self.toggle_sync_settings(self.enabled_check.isChecked())

    def _add_time_to_list(self, list_widget, hour_spin, minute_spin):
        time_str = f"{hour_spin.value():02d}:{minute_spin.value():02d}"
        # 检查重复
        for i in range(list_widget.count()):
            if list_widget.item(i).text() == time_str:
                QMessageBox.warning(self, "提示", "该时间已存在")
                return
        list_widget.addItem(time_str)

    def _remove_selected_time(self, list_widget):
        current_row = list_widget.currentRow()
        if current_row >= 0:
            list_widget.takeItem(current_row)

    def _get_times_from_list(self, list_widget):
        times = []
        for i in range(list_widget.count()):
            times.append(list_widget.item(i).text())
        return times if times else ['00:00']

    def _set_times_to_list(self, list_widget, times):
        list_widget.clear()
        for t in times:
            list_widget.addItem(t)

    def toggle_sync_settings(self, state):
        enabled = state == Qt.Checked
        self.sync_type_combo.setEnabled(enabled)
        self.interval_widget.setEnabled(enabled)
        self.monthly_widget.setEnabled(enabled)
        self.weekly_widget.setEnabled(enabled)
        self.daily_widget.setEnabled(enabled)

    def change_sync_type(self, index):
        self.interval_widget.hide()
        self.monthly_widget.hide()
        self.weekly_widget.hide()
        self.daily_widget.hide()

        if index == 0:
            self.interval_widget.show()
        elif index == 1:
            self.monthly_widget.show()
        elif index == 2:
            self.weekly_widget.show()
        elif index == 3:
            self.daily_widget.show()

    def check_monthly_days_warning(self):
        selected_days = [i + 1 for i, check in enumerate(self.monthly_day_checks) if check.isChecked()]
        big_days = [d for d in selected_days if d > 28]
        if big_days:
            days_str = ','.join(map(str, big_days))
            self.monthly_warning_label.setText(f"提示：{days_str}日在小月/2月可能自动跳过")
        else:
            self.monthly_warning_label.setText("")

    def browse_local_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择本地目录", "")
        if dir_path:
            self.local_dir_edit.setText(dir_path)

    def load_config(self):
        self.name_edit.setText(self.config.name)
        self.hostname_edit.setText(self.config.hostname)
        self.port_spin.setValue(self.config.port)
        self.username_edit.setText(self.config.username)
        self.password_edit.setText(self.config.password)
        self.root_password_edit.setText(getattr(self.config, 'root_password', ''))
        self.remote_dir_edit.setText(self.config.remote_dir)
        self.local_dir_edit.setText(self.config.local_dir)
        self.enabled_check.setChecked(self.config.enabled)

        sync_type = getattr(self.config, 'sync_type', 'interval')
        if sync_type == 'interval':
            self.sync_type_combo.setCurrentIndex(0)
            self.sync_interval_spin.setValue(getattr(self.config, 'sync_interval', 60))
        elif sync_type == 'monthly':
            self.sync_type_combo.setCurrentIndex(1)
            monthly_days = getattr(self.config, 'monthly_days', [])
            for i, check in enumerate(self.monthly_day_checks):
                check.setChecked((i + 1) in monthly_days)
            monthly_times = getattr(self.config, 'monthly_times', ['00:00'])
            self._set_times_to_list(self.monthly_time_list, monthly_times)
        elif sync_type == 'weekly':
            self.sync_type_combo.setCurrentIndex(2)
            weekly_days = getattr(self.config, 'weekly_days', [])
            for i, check in enumerate(self.weekly_day_checks):
                check.setChecked(i in weekly_days)
            weekly_times = getattr(self.config, 'weekly_times', ['00:00'])
            self._set_times_to_list(self.weekly_time_list, weekly_times)
        elif sync_type == 'daily':
            self.sync_type_combo.setCurrentIndex(3)
            daily_times = getattr(self.config, 'daily_times', ['00:00'])
            self._set_times_to_list(self.daily_time_list, daily_times)

    def validate_and_accept(self):
        if not self.name_edit.text():
            QMessageBox.warning(self, "提示", "请输入任务名称")
            return
        if not self.hostname_edit.text():
            QMessageBox.warning(self, "提示", "请输入服务器地址")
            return
        if not self.username_edit.text():
            QMessageBox.warning(self, "提示", "请输入用户名")
            return
        if not self.password_edit.text():
            QMessageBox.warning(self, "提示", "请输入密码")
            return
        if not self.remote_dir_edit.text():
            QMessageBox.warning(self, "提示", "请输入远程目录")
            return
        if not self.local_dir_edit.text():
            QMessageBox.warning(self, "提示", "请选择本地目录")
            return

        if self.enabled_check.isChecked():
            sync_type_index = self.sync_type_combo.currentIndex()
            if sync_type_index == 1:
                selected_days = [i + 1 for i, check in enumerate(self.monthly_day_checks) if check.isChecked()]
                if not selected_days:
                    QMessageBox.warning(self, "提示", "请选择至少一个日期")
                    return
            elif sync_type_index == 2:
                selected_days = [i for i, check in enumerate(self.weekly_day_checks) if check.isChecked()]
                if not selected_days:
                    QMessageBox.warning(self, "提示", "请选择至少一个星期")
                    return

        self.accept()

    def get_config(self):
        enabled = self.enabled_check.isChecked()
        sync_type_index = self.sync_type_combo.currentIndex()

        sync_type = 'interval'
        sync_interval = 0
        monthly_days = []
        monthly_times = ['00:00']
        weekly_days = []
        weekly_times = ['00:00']
        daily_times = ['00:00']

        if enabled:
            if sync_type_index == 0:
                sync_type = 'interval'
                sync_interval = self.sync_interval_spin.value()
            elif sync_type_index == 1:
                sync_type = 'monthly'
                monthly_days = [i + 1 for i, check in enumerate(self.monthly_day_checks) if check.isChecked()]
                monthly_times = self._get_times_from_list(self.monthly_time_list)
            elif sync_type_index == 2:
                sync_type = 'weekly'
                weekly_days = [i for i, check in enumerate(self.weekly_day_checks) if check.isChecked()]
                weekly_times = self._get_times_from_list(self.weekly_time_list)
            elif sync_type_index == 3:
                sync_type = 'daily'
                daily_times = self._get_times_from_list(self.daily_time_list)

        return ServerConfig(
            id="",
            name=self.name_edit.text(),
            hostname=self.hostname_edit.text(),
            port=self.port_spin.value(),
            username=self.username_edit.text(),
            password=self.password_edit.text(),
            root_password=self.root_password_edit.text(),
            remote_dir=self.remote_dir_edit.text(),
            local_dir=self.local_dir_edit.text(),
            sync_type=sync_type,
            sync_interval=sync_interval,
            monthly_days=monthly_days,
            monthly_times=monthly_times,
            weekly_days=weekly_days,
            weekly_times=weekly_times,
            daily_times=daily_times,
            enabled=enabled
        )

class ProgressDialog(QDialog):
    sync_finished = pyqtSignal(bool, str, str)
    progress_updated = pyqtSignal(int, str)
    
    def __init__(self, parent, config, is_scheduled=False):
        super().__init__(parent)
        self.setWindowTitle(f"正在同步: {config.name}")
        self.setGeometry(350, 300, 450, 180)
        if not is_scheduled:
            self.setModal(True)
        else:
            self.setWindowFlags(Qt.Window | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowIcon(parent.windowIcon())
        
        self.setStyle(QStyleFactory.create('Fusion'))
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(240, 240, 245))
        self.setPalette(palette)
        
        self.config = config
        self.is_scheduled = is_scheduled
        self.sync_thread = None
        self.sync_completed = False
        self.sync_cancelled = False
        
        self.last_progress = -1
        self.last_progress_time = time.time()
        self.progress_timeout = 60
        self.progress_timeout_timer = QTimer(self)
        self.progress_timeout_timer.timeout.connect(self.check_progress_timeout)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.status_label = QLabel("准备同步...")
        self.status_label.setStyleSheet("QLabel { font-size: 14px; font-weight: 500; color: #333; }")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #e9ecef;
                border-radius: 6px;
                height: 20px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #007bff;
                border-radius: 4px;
            }
        """)
        
        self.btn_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setStyleSheet("QPushButton { background-color: #6c757d; color: white; border: none; padding: 8px 20px; border-radius: 4px; font-size: 13px; } QPushButton:hover { background-color: #5a6268; }")
        self.cancel_btn.clicked.connect(self.cancel_sync)
        
        self.ok_btn = QPushButton("完成")
        self.ok_btn.setStyleSheet("QPushButton { background-color: #28a745; color: white; border: none; padding: 8px 20px; border-radius: 4px; font-size: 13px; } QPushButton:hover { background-color: #218838; }")
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.setEnabled(False)
        
        self.btn_layout.addStretch()
        self.btn_layout.addWidget(self.cancel_btn)
        self.btn_layout.addWidget(self.ok_btn)
        
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addLayout(self.btn_layout)
        
        self.setLayout(layout)
        
        self.sync_finished.connect(self.on_sync_finished)
        self.progress_updated.connect(self.on_progress_updated)
        
        self.log_to_file(f"ProgressDialog created for {config.name}, is_scheduled={is_scheduled}")
        
        self.sync_thread = threading.Thread(target=self.run_sync)
        self.sync_thread.start()
        
        self.progress_timeout_timer.start(5000)

    def run_sync(self):
        self.log_to_file(f"Starting sync for {self.config.name}")
        
        try:
            root_password = getattr(self.config, 'root_password', None)
            ssh = SSHSync(
                hostname=self.config.hostname,
                port=self.config.port,
                username=self.config.username,
                password=self.config.password,
                root_password=root_password
            )
            
            success, msg = ssh.connect()
            if not success:
                self.sync_finished.emit(False, f"连接失败: {msg}", self.config.name)
                return
            
            self.progress_updated.emit(0, "开始同步...")
            
            def progress_callback(completed, total):
                if total > 0:
                    progress = int((completed / total) * 100)
                    self.progress_updated.emit(progress, f"同步中: {completed}/{total}")
            
            success, msg = ssh.sync_directory(
                self.config.remote_dir,
                self.config.local_dir,
                progress_callback
            )
            
            ssh.disconnect()
            
            self.sync_finished.emit(success, msg, self.config.name)
            
        except Exception as e:
            self.log_to_file(f"Exception in run_sync: {str(e)}")
            self.sync_finished.emit(False, f"同步异常: {str(e)}", self.config.name)

    def on_progress_updated(self, progress, status_text):
        self.progress_bar.setValue(progress)
        self.status_label.setText(status_text)
        if progress != self.last_progress:
            self.last_progress = progress
            self.last_progress_time = time.time()

    def check_progress_timeout(self):
        if self.sync_completed:
            return
        elapsed = time.time() - self.last_progress_time
        if elapsed > self.progress_timeout:
            self.log_to_file(f"Progress timeout detected: {elapsed:.1f}s without progress")
            self.status_label.setText(f"同步较慢，已等待{int(elapsed)}秒...有可能是网络慢或文件过大导致，请耐心等待同步完成")

    def on_sync_finished(self, success, msg, task_name):
        self.sync_completed = True
        self.progress_timeout_timer.stop()
        
        if success:
            status_msg = msg
            progress_val = 100
        else:
            status_msg = msg
            progress_val = self.progress_bar.value()
        
        self.log_to_file(f"Sync result for {task_name}: success={success}, msg={msg}")
        
        main_window = self.parent()
        try:
            main_window.add_sync_log(task_name, success, msg)
            self.log_to_file("Log added successfully")
        except Exception as e:
            self.log_to_file(f"Failed to add sync log: {str(e)}")
        
        self.status_label.setText(status_msg)
        self.progress_bar.setValue(progress_val)
        
        if self.is_scheduled:
            QTimer.singleShot(500, self.accept)
        else:
            self.cancel_btn.setEnabled(False)
            self.ok_btn.setEnabled(True)
            self.ok_btn.setText("完成")

    def accept(self):
        self.log_to_file(f"ProgressDialog.accept() called, is_scheduled={self.is_scheduled}")
        super().accept()

    def reject(self):
        self.log_to_file(f"ProgressDialog.reject() called")
        super().reject()

    def close(self):
        self.log_to_file(f"ProgressDialog.close() called")
        super().close()

    def cancel_sync(self):
        if not self.sync_completed:
            self.log_to_file(f"Sync cancelled for {self.config.name}")
        self.close()
    
    def log_to_file(self, message):
        log_message("ProgressDialog", "INFO", message)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create('Fusion'))
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
