import sys
import traceback
import os
import atexit
import win32event
import win32api
from winerror import ERROR_ALREADY_EXISTS
from PyQt5.QtWidgets import QApplication, QMessageBox
from gui.main_window import MainWindow
from utils.logger import log_message, log_info, log_error, log_debug


def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    error_msg = f"未捕获的异常: {exc_type.__name__}: {exc_value}\n\n调用栈:\n{''.join(traceback.format_tb(exc_traceback))}"
    log_error(error_msg)
    print(f"[ERROR] 未捕获的异常: {error_msg}")

def handle_exit():
    log_info("程序正在退出")

sys.excepthook = handle_uncaught_exception
atexit.register(handle_exit)

def main():
    try:
        mutex = win32event.CreateMutex(None, False, "DateSync_Mutex")
        last_error = win32api.GetLastError()
        
        log_info("程序启动")
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        
        if last_error == ERROR_ALREADY_EXISTS:
            QMessageBox.critical(None, "程序已运行", "检测到程序已在运行中，请关闭现有程序后再启动。")
            log_error("检测到程序已在运行中")
            win32api.CloseHandle(mutex)
            sys.exit(0)
        
        window = MainWindow()
        window.show()
        log_info("主窗口已显示")
        exit_code = app.exec_()
        log_info(f"程序正常退出，退出码: {exit_code}")
        win32api.CloseHandle(mutex)
        sys.exit(exit_code)
    except Exception as e:
        error_msg = f"程序启动失败: {str(e)}\n\n详细信息:\n{traceback.format_exc()}"
        log_error(error_msg)
        try:
            QMessageBox.critical(None, "程序启动失败", f"程序启动失败，请查看日志文件。\n\n错误信息: {str(e)}\n\n日志位置: {os.path.expanduser('~')}\\DateSyncLogs")
        except:
            pass
        log_error(f"程序因启动失败退出: {error_msg}")
        sys.exit(1)

if __name__ == "__main__":
    main()
