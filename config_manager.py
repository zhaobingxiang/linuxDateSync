import json
import os
from utils.crypto import encrypt_password, decrypt_password

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".datesync_config.json")


def _resolve_time_list(data, new_key, old_key):
    """从配置数据中读取时间列表，兼容旧版单值格式"""
    val = data.get(new_key)
    if val is not None and isinstance(val, list):
        return val
    old_val = data.get(old_key)
    if old_val:
        return [old_val]
    return ['00:00']


class ServerConfig:
    def __init__(self, id, name, hostname, port, username, password, root_password,
                 remote_dir, local_dir, sync_type='interval', sync_interval=0,
                 monthly_days=None, monthly_times=None,
                 weekly_days=None, weekly_times=None,
                 daily_times=None, enabled=True, last_sync=0):
        self.id = id
        self.name = name
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.root_password = root_password
        self.remote_dir = remote_dir
        self.local_dir = local_dir
        self.sync_type = sync_type  # interval, monthly, weekly, daily
        self.sync_interval = sync_interval  # 分钟，用于interval类型
        self.monthly_days = monthly_days if monthly_days else []  # 1-31
        self.monthly_times = monthly_times if monthly_times else ['00:00']  # 支持多个时间
        self.weekly_days = weekly_days if weekly_days else []  # 0-6 (周一到周日)
        self.weekly_times = weekly_times if weekly_times else ['00:00']  # 支持多个时间
        self.daily_times = daily_times if daily_times else ['00:00']  # 支持多个时间
        self.enabled = enabled
        self.last_sync = last_sync

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'hostname': self.hostname,
            'port': self.port,
            'username': self.username,
            'password': encrypt_password(self.password),
            'root_password': encrypt_password(self.root_password),
            'remote_dir': self.remote_dir,
            'local_dir': self.local_dir,
            'sync_type': self.sync_type,
            'sync_interval': self.sync_interval,
            'monthly_days': self.monthly_days,
            'monthly_times': self.monthly_times,
            'weekly_days': self.weekly_days,
            'weekly_times': self.weekly_times,
            'daily_times': self.daily_times,
            'enabled': self.enabled,
            'last_sync': self.last_sync
        }

    @classmethod
    def from_dict(cls, data):
        config = cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            hostname=data.get('hostname', ''),
            port=data.get('port', 22),
            username=data.get('username', ''),
            password=decrypt_password(data.get('password', '')),
            root_password=decrypt_password(data.get('root_password', '')),
            remote_dir=data.get('remote_dir', ''),
            local_dir=data.get('local_dir', ''),
            sync_type=data.get('sync_type', 'interval'),
            sync_interval=data.get('sync_interval', 0),
            monthly_days=data.get('monthly_days', []),
            monthly_times=_resolve_time_list(data, 'monthly_times', 'monthly_time'),
            weekly_days=data.get('weekly_days', []),
            weekly_times=_resolve_time_list(data, 'weekly_times', 'weekly_time'),
            daily_times=_resolve_time_list(data, 'daily_times', 'daily_time'),
            enabled=data.get('enabled', True),
            last_sync=data.get('last_sync', 0)
        )
        return config

class ConfigManager:
    def __init__(self):
        self.configs = []
        self.load_configs()

    def load_configs(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.configs = [ServerConfig.from_dict(item) for item in data.get('servers', [])]
        except Exception:
            self.configs = []

    def save_configs(self):
        try:
            data = {'servers': [config.to_dict() for config in self.configs]}
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            return True, "保存成功"
        except Exception as e:
            return False, str(e)

    def add_config(self, config):
        self.configs.append(config)
        return self.save_configs()

    def update_config(self, config_id, updated_config):
        for i, config in enumerate(self.configs):
            if config.id == config_id:
                updated_config.last_sync = config.last_sync
                self.configs[i] = updated_config
                return self.save_configs()
        return False, "配置不存在"

    def delete_config(self, config_id):
        for i, config in enumerate(self.configs):
            if config.id == config_id:
                del self.configs[i]
                return self.save_configs()
        return False, "配置不存在"

    def get_config(self, config_id):
        for config in self.configs:
            if config.id == config_id:
                return config
        return None

    def get_all_configs(self):
        return self.configs
    
    def update_last_sync(self, config_id, last_sync_time):
        for config in self.configs:
            if config.id == config_id:
                config.last_sync = last_sync_time
                self.save_configs()
                break