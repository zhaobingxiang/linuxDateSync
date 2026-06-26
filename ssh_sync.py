import paramiko
import os
from stat import S_ISDIR, S_ISREG
from utils.logger import log_message, log_info, log_error, log_debug

class SSHSync:
    def __init__(self, hostname, port, username, password, root_password=None):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.root_password = root_password
        self.client = None
        self.sftp = None
        self.is_root = False

    def connect(self):
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            self.client.connect(
                hostname=self.hostname,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=10
            )
            
            if self.username == 'root':
                self.sftp = self.client.open_sftp()
                self.is_root = True
                return True, "连接成功（已以root身份登录）"
            
            self.sftp = self.client.open_sftp()
            return True, "连接成功"
        except Exception as e:
            return False, str(e)
    
    def check_connection(self):
        """简单检查SSH连接是否可用，不打开SFTP"""
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                hostname=self.hostname,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=5
            )
            client.close()
            return True, "连接成功"
        except Exception as e:
            return False, str(e)

    def execute_command(self, command, use_sudo=False):
        """执行SSH命令"""
        try:
            if use_sudo and self.root_password and self.username != 'root':
                return self._execute_with_sudo(command)
            
            stdin, stdout, stderr = self.client.exec_command(command)
            stdout.channel.set_combine_stderr(True)
            output = stdout.read().decode('utf-8')
            exit_status = stdout.channel.recv_exit_status()
            
            return exit_status == 0, output
        except Exception as e:
            return False, str(e)
    
    def _execute_with_sudo(self, command):
        """使用 invoke_shell 安全执行 sudo 命令"""
        try:
            shell = self.client.invoke_shell()
            shell.settimeout(30)

            full_command = f"sudo -S {command}\n"
            shell.send(full_command)

            import time
            time.sleep(0.5)
            shell.send(f"{self.root_password}\n")

            output = ""
            start_time = time.time()
            while time.time() - start_time < 30:
                if shell.recv_ready():
                    output += shell.recv(4096).decode('utf-8', errors='ignore')
                    if output.endswith('$ ') or output.endswith('# '):
                        break
                time.sleep(0.1)
            
            shell.close()
            
            lines = output.strip().split('\n')
            if len(lines) > 1:
                result_lines = lines[1:]
                result = '\n'.join(result_lines).strip()
            else:
                result = output.strip()
            
            exit_code = 0 if 'Permission denied' not in result else 1
            return exit_code == 0, result
        except Exception as e:
            return False, str(e)

    def disconnect(self):
        if self.sftp:
            self.sftp.close()
        if self.client:
            self.client.close()

    def list_files(self, remote_path):
        try:
            try:
                files = []
                for item in self.sftp.listdir_attr(remote_path):
                    files.append({
                        'filename': item.filename,
                        'size': item.st_size,
                        'mtime': item.st_mtime,
                        'is_dir': S_ISDIR(item.st_mode)
                    })
                self.log_to_file(f"SFTP list_files成功: {remote_path}, 文件数: {len(files)}")
                return True, files
            except Exception as e:
                error_msg = str(e)
                self.log_to_file(f"SFTP list_files失败: {remote_path}, 错误: {error_msg}")
                if "Permission denied" in error_msg and self.root_password and self.username != 'root':
                    self.log_to_file(f"尝试使用sudo列出目录: {remote_path}")
                    return self.list_files_with_sudo(remote_path)
                return False, error_msg
        except Exception as e:
            error_msg = str(e)
            self.log_to_file(f"list_files异常: {error_msg}")
            return False, error_msg

    def list_files_with_sudo(self, remote_path):
        """使用sudo列出目录"""
        try:
            command = f"find '{remote_path}' -maxdepth 1 -mindepth 1 -printf '%y|%s|%f\\0'"
            self.log_to_file(f"执行命令: {command}")
            success, output = self.execute_command(command, use_sudo=True)
            
            self.log_to_file(f"命令执行结果: success={success}, output={output[:500]}")
            
            if not success:
                return False, f"无法列出目录: {output}"
            
            files = []
            entries = output.strip('\0').split('\0')
            for entry in entries:
                if not entry:
                    continue
                parts = entry.split('|', 2)
                if len(parts) != 3:
                    continue
                file_type, size_str, filename = parts
                if filename in ('.', '..'):
                    continue
                is_dir = file_type == 'd'
                try:
                    size = int(size_str)
                except ValueError:
                    size = 0
                files.append({
                    'filename': filename,
                    'size': size,
                    'mtime': 0,
                    'is_dir': is_dir
                })
            
            self.log_to_file(f"sudo list_files成功: {remote_path}, 文件数: {len(files)}")
            return True, files
        except Exception as e:
            error_msg = str(e)
            self.log_to_file(f"list_files_with_sudo异常: {error_msg}")
            return False, error_msg

    def sync_directory(self, remote_dir, local_dir, progress_callback=None, total_items=None, completed_items=None):
        try:
            import time as time_module
            start_time = time_module.time()
            
            if not os.path.exists(local_dir):
                os.makedirs(local_dir)

            self.log_to_file(f"[{time_module.time():.2f}] 开始列出目录: {remote_dir}")
            success, items = self.list_files(remote_dir)
            self.log_to_file(f"[{time_module.time():.2f}] 目录列表完成，共 {len(items)} 个项目")
            if not success:
                return False, items
            
            # 首次调用时，先递归统计总文件和目录数
            if total_items is None:
                total_items = self._count_total_items(items, remote_dir)
                completed_items = [0]
            
            total_files = 0
            total_dirs = 0
            skipped_files = 0
            skipped_dirs = 0
            error_messages = []
            import re

            for idx, item in enumerate(items):
                item_start = time_module.time()
                remote_path = f"{remote_dir.rstrip('/')}/{item['filename']}"
                local_path = os.path.join(local_dir, item['filename'])
                self.log_to_file(f"[{time_module.time():.2f}] 处理第 {idx+1}/{len(items)} 个项目: {item['filename']}")

                if item['is_dir']:
                    total_dirs += 1
                    success, msg = self.sync_directory(
                        remote_path, local_path, progress_callback,
                        total_items, completed_items
                    )
                    if not success:
                        self.log_to_file(f"跳过目录 {remote_path}: {msg}")
                        error_messages.append(f"跳过目录: {item['filename']} ({msg})")
                        skipped_dirs += 1
                    else:
                        # 从返回消息中提取子目录的统计信息
                        file_match = re.search(r'(\d+)\s*个文件', msg)
                        dir_match = re.search(r'(\d+)\s*个目录', msg)
                        if file_match:
                            total_files += int(file_match.group(1))
                        if dir_match:
                            total_dirs += int(dir_match.group(1))
                else:
                    self.log_to_file(f"[{time_module.time():.2f}] 开始下载文件: {remote_path}")
                    success, msg = self.download_file(remote_path, local_path)
                    self.log_to_file(f"[{time_module.time():.2f}] 文件下载完成: {remote_path}, 耗时 {time_module.time()-item_start:.2f}s")
                    if not success:
                        self.log_to_file(f"跳过文件 {remote_path}: {msg}")
                        error_messages.append(f"跳过文件: {item['filename']} ({msg})")
                        skipped_files += 1
                    total_files += 1
                
                # 更新进度
                if progress_callback and total_items > 0:
                    completed_items[0] += 1
                    progress_callback(
                        completed_items[0], total_items,
                        f"正在同步: {item['filename']}"
                    )

            if skipped_files > 0 or skipped_dirs > 0:
                warning_msg = f"同步完成，共 {total_files} 个文件，{total_dirs} 个目录"
                if skipped_dirs > 0:
                    warning_msg += f"，跳过 {skipped_dirs} 个目录"
                if skipped_files > 0:
                    warning_msg += f"，跳过 {skipped_files} 个文件"
                if error_messages:
                    warning_msg += "\n跳过原因: " + "; ".join(error_messages[:5])
                    if len(error_messages) > 5:
                        warning_msg += f" (还有 {len(error_messages) - 5} 个)"
                return True, warning_msg
            else:
                return True, f"同步完成，共 {total_files} 个文件，{total_dirs} 个目录"
        except Exception as e:
            return False, str(e)
    
    def _count_total_items(self, items, remote_dir):
        """递归统计总文件和目录数"""
        total = 0
        for item in items:
            total += 1
            if item['is_dir']:
                try:
                    remote_path = f"{remote_dir.rstrip('/')}/{item['filename']}"
                    success, sub_items = self.list_files(remote_path)
                    if success:
                        total += self._count_total_items(sub_items, remote_path)
                except Exception:
                    pass
        return total

    def download_file(self, remote_path, local_path):
        """下载文件，支持root权限"""
        try:
            try:
                self.sftp.get(remote_path, local_path)
                self.log_to_file(f"SFTP下载成功: {remote_path} -> {local_path}")
                return True, "下载成功"
            except Exception as e:
                error_msg = str(e)
                self.log_to_file(f"SFTP下载失败: {remote_path}, 错误: {error_msg}")
                if "Permission denied" in error_msg and self.root_password and self.username != 'root':
                    self.log_to_file(f"尝试使用sudo下载: {remote_path}")
                    return self.download_file_with_sudo(remote_path, local_path)
                return False, error_msg
        except Exception as e:
            error_msg = str(e)
            self.log_to_file(f"download_file异常: {error_msg}")
            return False, error_msg

    def download_file_with_sudo(self, remote_path, local_path):
        """使用 sudo 下载文件
        
        方法：
        1. 在远程服务器上使用 mktemp 创建安全的临时文件
        2. 使用 sudo 复制源文件到临时文件
        3. 使用 sudo 修改临时文件权限为可读
        4. 通过 SFTP 下载临时文件
        5. 清理远程临时文件
        """
        try:
            self.log_to_file(f"download_file_with_sudo: remote_path={remote_path}, local_path={local_path}")
            
            # 在远程服务器上使用 mktemp 创建安全的临时文件路径
            basename = os.path.basename(remote_path)
            mktemp_command = f"mktemp /tmp/{basename}.XXXXXXXXXX"
            success, output = self.execute_command(mktemp_command, use_sudo=False)
            
            if not success or not output.strip():
                error_msg = f"无法创建远程临时文件：{output}"
                self.log_to_file(f"sudo 下载失败 (mktemp): {error_msg}")
                return False, error_msg
            
            remote_temp_path = output.strip()
            self.log_to_file(f"远程临时文件路径: {remote_temp_path}")
            
            # 使用 sudo 复制文件到临时位置
            copy_command = f"cp '{remote_path}' '{remote_temp_path}'"
            self.log_to_file(f"执行复制命令：{copy_command}")
            
            success, output = self.execute_command(copy_command, use_sudo=True)
            
            if not success:
                error_msg = f"无法复制远程文件：{output}"
                self.log_to_file(f"sudo 下载失败 (复制): {error_msg}")
                self._cleanup_remote_temp(remote_temp_path)
                return False, error_msg
            
            # 修改临时文件权限为可读
            chmod_command = f"chmod 644 '{remote_temp_path}'"
            self.log_to_file(f"执行 chmod 命令：{chmod_command}")
            
            success, output = self.execute_command(chmod_command, use_sudo=True)
            
            if not success:
                self.log_to_file(f"chmod 失败，但继续尝试下载：{output}")
            
            # 通过 SFTP 下载临时文件
            self.log_to_file(f"通过 SFTP 下载临时文件：{remote_temp_path} -> {local_path}")
            
            try:
                self.sftp.get(remote_temp_path, local_path)
                self.log_to_file(f"SFTP 下载临时文件成功")
            except Exception as e:
                error_msg = f"SFTP 下载临时文件失败：{str(e)}"
                self.log_to_file(error_msg)
                self._cleanup_remote_temp(remote_temp_path)
                return False, error_msg
            
            # 删除远程临时文件
            self._cleanup_remote_temp(remote_temp_path)
            
            self.log_to_file(f"sudo 下载成功：{remote_path} -> {local_path}")
            return True, "下载成功（使用 sudo）"
        except Exception as e:
            error_msg = str(e)
            self.log_to_file(f"download_file_with_sudo 异常：{error_msg}")
            return False, error_msg
    
    def _cleanup_remote_temp(self, temp_path):
        """清理远程临时文件"""
        try:
            rm_command = f"rm -f '{temp_path}'"
            self.log_to_file(f"执行清理命令：{rm_command}")
            self.execute_command(rm_command, use_sudo=False)
        except Exception:
            pass

    def log_to_file(self, message):
        """记录日志到文件"""
        log_message("SSHSync", "INFO", message)

    def get_remote_file_size(self, remote_path):
        try:
            attr = self.sftp.stat(remote_path)
            return attr.st_size
        except Exception as e:
            return 0
