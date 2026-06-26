import datetime
import os

# 日志级别常量
LOG_LEVEL_DEBUG = 0
LOG_LEVEL_INFO = 1
LOG_LEVEL_ERROR = 2

# 当前日志级别（默认 INFO）
_current_log_level = LOG_LEVEL_INFO

def set_log_level(level):
    """设置日志级别
    
    Args:
        level: 日志级别，可以是 LOG_LEVEL_DEBUG, LOG_LEVEL_INFO, LOG_LEVEL_ERROR
               也可以是字符串 'DEBUG', 'INFO', 'ERROR'
    """
    global _current_log_level
    
    if isinstance(level, str):
        level = level.upper()
        if level == 'DEBUG':
            _current_log_level = LOG_LEVEL_DEBUG
        elif level == 'INFO':
            _current_log_level = LOG_LEVEL_INFO
        elif level == 'ERROR':
            _current_log_level = LOG_LEVEL_ERROR
        else:
            raise ValueError(f"无效的日志级别: {level}")
    elif isinstance(level, int):
        if level in [LOG_LEVEL_DEBUG, LOG_LEVEL_INFO, LOG_LEVEL_ERROR]:
            _current_log_level = level
        else:
            raise ValueError(f"无效的日志级别: {level}")
    else:
        raise TypeError("日志级别必须是字符串或整数")

def get_log_level():
    """获取当前日志级别"""
    level_map = {
        LOG_LEVEL_DEBUG: 'DEBUG',
        LOG_LEVEL_INFO: 'INFO',
        LOG_LEVEL_ERROR: 'ERROR'
    }
    return level_map.get(_current_log_level, 'INFO')

def get_log_file():
    """获取日志文件路径"""
    user_dir = os.path.expanduser("~")
    log_dir = os.path.join(user_dir, "DateSyncLogs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"datesync_{datetime.date.today().strftime('%Y%m%d')}.log")
    return log_file

def log_message(module, level, message):
    """记录日志到文件
    
    Args:
        module: 模块名称，如 'Main', 'SSHSync', 'TimeSync'
        level: 日志级别，如 'INFO', 'ERROR', 'DEBUG'
        message: 日志消息
    """
    # 根据日志级别过滤
    level_priority = {
        'DEBUG': LOG_LEVEL_DEBUG,
        'INFO': LOG_LEVEL_INFO,
        'ERROR': LOG_LEVEL_ERROR
    }
    
    if level_priority.get(level, LOG_LEVEL_INFO) < _current_log_level:
        return
    
    log_file = get_log_file()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{now}] [{module}] [{level}] {message}\n")

def log_info(message, module="Main"):
    """记录 INFO 级别日志"""
    log_message(module, "INFO", message)

def log_error(message, module="Main"):
    """记录 ERROR 级别日志"""
    log_message(module, "ERROR", message)

def log_debug(message, module="Main"):
    """记录 DEBUG 级别日志"""
    log_message(module, "DEBUG", message)
