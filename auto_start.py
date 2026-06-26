import winreg
import os
import sys

class AutoStartManager:
    def __init__(self):
        self.reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        self.app_name = "DateSync"

    def is_auto_start_enabled(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.reg_path, 0, winreg.KEY_READ)
            value, _ = winreg.QueryValueEx(key, self.app_name)
            winreg.CloseKey(key)
            return True, value
        except FileNotFoundError:
            return False, ""
        except Exception as e:
            return False, str(e)

    def set_auto_start(self, enabled, exe_path=None):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.reg_path, 0, winreg.KEY_ALL_ACCESS)
            
            if enabled:
                if not exe_path:
                    exe_path = os.path.abspath(sys.argv[0])
                winreg.SetValueEx(key, self.app_name, 0, winreg.REG_SZ, exe_path)
                winreg.CloseKey(key)
                return True, "开机自启动已启用"
            else:
                winreg.DeleteValue(key, self.app_name)
                winreg.CloseKey(key)
                return True, "开机自启动已禁用"
        except FileNotFoundError:
            if enabled:
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.reg_path)
                if not exe_path:
                    exe_path = os.path.abspath(sys.argv[0])
                winreg.SetValueEx(key, self.app_name, 0, winreg.REG_SZ, exe_path)
                winreg.CloseKey(key)
                return True, "开机自启动已启用"
            return False, "键不存在"
        except Exception as e:
            return False, str(e)
