from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QMessageBox
)
from PyQt5.QtCore import Qt
from utils.logger import (
    set_log_level, get_log_level,
    LOG_LEVEL_DEBUG, LOG_LEVEL_INFO, LOG_LEVEL_ERROR
)


class LogLevelDialog(QDialog):
    """日志级别设置对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("日志级别设置")
        self.setMinimumWidth(400)
        self.setMinimumHeight(200)

        layout = QVBoxLayout(self)

        # 说明标签
        info_label = QLabel(
            "选择日志记录级别：\n"
            "• DEBUG：记录所有日志（详细调试信息）\n"
            "• INFO：记录正常信息和错误（默认）\n"
            "• ERROR：仅记录错误信息"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("padding: 10px; background-color: #f0f0f5; border-radius: 4px;")
        layout.addWidget(info_label)

        # 级别选择
        level_layout = QHBoxLayout()
        level_label = QLabel("当前级别：")
        level_label.setStyleSheet("font-weight: bold;")
        level_layout.addWidget(level_label)

        self.level_combo = QComboBox()
        self.level_combo.addItem("DEBUG（详细）", LOG_LEVEL_DEBUG)
        self.level_combo.addItem("INFO（默认）", LOG_LEVEL_INFO)
        self.level_combo.addItem("ERROR（仅错误）", LOG_LEVEL_ERROR)

        # 设置当前选中的级别
        current_level = get_log_level()
        if current_level == "DEBUG":
            self.level_combo.setCurrentIndex(0)
        elif current_level == "ERROR":
            self.level_combo.setCurrentIndex(2)
        else:
            self.level_combo.setCurrentIndex(1)

        level_layout.addWidget(self.level_combo)
        level_layout.addStretch()
        layout.addLayout(level_layout)

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        apply_btn = QPushButton("应用")
        apply_btn.setStyleSheet(
            "QPushButton { background-color: #3366cc; color: white; "
            "padding: 8px 20px; border: none; border-radius: 4px; }"
            "QPushButton:hover { background-color: #4477dd; }"
        )
        apply_btn.clicked.connect(self.apply_log_level)
        button_layout.addWidget(apply_btn)

        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(
            "QPushButton { background-color: #6c757d; color: white; "
            "padding: 8px 20px; border: none; border-radius: 4px; }"
            "QPushButton:hover { background-color: #7c858d; }"
        )
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def apply_log_level(self):
        """应用日志级别设置"""
        level_value = self.level_combo.currentData()
        level_name = self.level_combo.currentText().split("（")[0]

        set_log_level(level_value)

        from utils.logger import log_info
        log_info(f"日志级别已修改为: {level_name}")

        QMessageBox.information(
            self,
            "设置成功",
            f"日志级别已设置为：{level_name}\n\n"
            f"• DEBUG：记录所有日志\n"
            f"• INFO：记录正常信息和错误\n"
            f"• ERROR：仅记录错误"
        )
