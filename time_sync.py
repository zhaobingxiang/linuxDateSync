import socket
import struct
import time
import datetime
import ctypes
from utils.logger import log_message, log_info, log_error, log_debug

class TimeSync:
    def __init__(self):
        self.timeout = 5  # 单个服务器超时时间（秒）
        self.port = 123
        self.last_error = ""
        self.total_timeout = 30  # 整体超时时间（秒）
    
    NTP_SERVERS = [
        'time.windows.com',
        'pool.ntp.org',
        'ntp.ntsc.ac.cn',
        'time.google.com',
        'cn.ntp.org.cn',
    ]
    
    def log(self, message):
        log_message("TimeSync", "INFO", message)
    
    def get_ntp_time(self, server):
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client.settimeout(self.timeout)
            
            data = b'\x1b' + 47 * b'\x00'
            
            self.log(f"Sending NTP request to {server}:{self.port}")
            client.sendto(data, (server, self.port))
            data, address = client.recvfrom(1024)
            
            if data:
                seconds = struct.unpack('>I', data[40:44])[0]
                fraction = struct.unpack('>I', data[44:48])[0]
                
                ntp_epoch = 2208988800
                unix_time = seconds - ntp_epoch + fraction / (2**32)
                
                client.close()
                self.log(f"Received NTP time: {unix_time}")
                return unix_time
            
        except socket.timeout:
            self.last_error = "连接超时"
            self.log(f"Error: Connection timeout")
        except socket.error as e:
            self.last_error = f"网络错误: {str(e)}"
            self.log(f"Error: Socket error - {str(e)}")
        except Exception as e:
            self.last_error = f"未知错误: {str(e)}"
            self.log(f"Error: {str(e)}")
        
        try:
            client.close()
        except:
            pass
        
        return None
    
    def get_current_ntp_server(self):
        """获取当前系统NTP服务器配置"""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                               r'SYSTEM\CurrentControlSet\Services\W32Time\Parameters')
            value, _ = winreg.QueryValueEx(key, 'NtpServer')
            winreg.CloseKey(key)
            return value
        except:
            return None
    
    def set_ntp_server(self, server):
        """设置系统NTP服务器配置"""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                               r'SYSTEM\CurrentControlSet\Services\W32Time\Parameters',
                               0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, 'NtpServer', 0, winreg.REG_SZ, server)
            winreg.CloseKey(key)
            return True
        except:
            return False
    
    def sync_time_from_server(self, server='time.windows.com'):
        """从指定NTP服务器同步时间"""
        ntp_time = self.get_ntp_time(server)
        if ntp_time:
            return self.set_system_time(ntp_time), ntp_time
        return False, None
    
    def set_system_time(self, timestamp):
        try:
            dt = datetime.datetime.fromtimestamp(timestamp)
            
            class SYSTEMTIME(ctypes.Structure):
                _fields_ = [
                    ('wYear', ctypes.c_short),
                    ('wMonth', ctypes.c_short),
                    ('wDayOfWeek', ctypes.c_short),
                    ('wDay', ctypes.c_short),
                    ('wHour', ctypes.c_short),
                    ('wMinute', ctypes.c_short),
                    ('wSecond', ctypes.c_short),
                    ('wMilliseconds', ctypes.c_short)
                ]
            
            st = SYSTEMTIME()
            st.wYear = dt.year
            st.wMonth = dt.month
            st.wDayOfWeek = dt.weekday()
            st.wDay = dt.day
            st.wHour = dt.hour
            st.wMinute = dt.minute
            st.wSecond = dt.second
            st.wMilliseconds = int(dt.microsecond / 1000)
            
            result = ctypes.windll.kernel32.SetLocalTime(ctypes.byref(st))
            if result == 0:
                error_code = ctypes.get_last_error()
                self.log(f"SetLocalTime failed with error code: {error_code}")
                return False
            
            return True
            
        except Exception as e:
            return False
    
    def sync_with_backup(self):
        """执行校时操作，使用多个备选服务器"""
        original_server = self.get_current_ntp_server()
        success = False
        error_msg = ""
        self.last_error = ""
        start_time = time.time()
        failed_servers = []
        
        self.log("Starting time sync with backup servers")
        
        try:
            # 尝试所有备选服务器
            for server in self.NTP_SERVERS:
                # 检查整体超时
                elapsed = time.time() - start_time
                if elapsed >= self.total_timeout:
                    error_msg = f"校时超时（总超时时间 {self.total_timeout} 秒）\n\n尝试过的服务器：\n" + "\n".join(f"  - {s[0]}: {s[1]}" for s in failed_servers)
                    self.log(f"Time sync total timeout exceeded: {self.total_timeout}s")
                    break
                
                self.log(f"Trying NTP server: {server}")
                result = self.sync_time_from_server(server)
                success = result[0]
                ntp_time = result[1]
                
                if success:
                    error_msg = f"校时成功（使用 {server}），同步时间为 {datetime.datetime.fromtimestamp(ntp_time)}"
                    self.log(f"Time sync successful from {server}: {datetime.datetime.fromtimestamp(ntp_time)}")
                    break
                else:
                    failed_servers.append((server, self.last_error))
                    self.log(f"Failed to sync from {server}: {self.last_error}")
            else:
                # 所有服务器都失败了
                error_msg = "校时失败！无法从任何 NTP 服务器获取网络时间。\n\n尝试过的服务器：\n" + "\n".join(f"  - {s[0]}: {s[1]}" for s in failed_servers) + "\n\n请检查网络连接或防火墙设置。"
                self.log(f"All NTP servers failed")
                
        except Exception as e:
            error_msg = f"校时过程中发生错误：{str(e)}\n\n尝试过的服务器：\n" + "\n".join(f"  - {s[0]}: {s[1]}" for s in failed_servers)
            self.log(f"Exception during time sync: {str(e)}")
        finally:
            if original_server:
                self.set_ntp_server(original_server)
                self.log(f"Restored original NTP server: {original_server}")
        
        return success, error_msg