"""
每日定时邮件服务
扫描指定文件夹下所有文件，以附件形式发送邮件
支持文本、图片、视频等任意类型文件
"""
import logging
import mimetypes
import os
import smtplib
import ssl
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import yaml

log = logging.getLogger('Qdestiny')

CONFIG_PATH = Path(__file__).parent / 'config.yaml'


def _load_email_config() -> dict:
    """加载邮件配置"""
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config.get('email', {})


def _scan_files(content_dir: str) -> list:
    """扫描目录下所有文件（不递归子目录）"""
    folder = Path(content_dir)
    if not folder.exists():
        log.error(f"[daily_email] 内容目录不存在: {content_dir}")
        return []
    if not folder.is_dir():
        log.error(f"[daily_email] 路径不是目录: {content_dir}")
        return []
    files = [f for f in sorted(folder.iterdir()) if f.is_file()]
    return files


def _build_message(email_cfg: dict, files: list) -> MIMEMultipart:
    """构建邮件消息"""
    today = datetime.now().strftime('%Y-%m-%d')

    msg = MIMEMultipart()
    msg['From'] = email_cfg['sender']
    msg['To'] = ', '.join(email_cfg['recipients'])
    msg['Subject'] = email_cfg.get('subject', '每日邮件 - {date}').replace('{date}', today)

    # 邮件正文
    body_template = email_cfg.get('body', '以下为 {date} 的附件内容，共 {count} 个文件，请查收。')
    body_text = body_template.replace('{date}', today).replace('{count}', str(len(files)))
    msg.attach(MIMEText(body_text, 'plain', 'utf-8'))

    # 添加附件
    for file_path in files:
        _attach_file(msg, file_path)

    return msg


def _attach_file(msg: MIMEMultipart, file_path: Path):
    """将文件作为附件添加到邮件"""
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if mime_type is None:
        mime_type = 'application/octet-stream'

    main_type, sub_type = mime_type.split('/', 1)

    try:
        with open(file_path, 'rb') as f:
            part = MIMEBase(main_type, sub_type)
            part.set_payload(f.read())
        encoders.encode_base64(part)
        # 使用 RFC 2231 编码文件名以支持中文
        part.add_header(
            'Content-Disposition', 'attachment',
            filename=('utf-8', '', file_path.name)
        )
        msg.attach(part)
    except Exception as e:
        log.warning(f"[daily_email] 附加文件失败 {file_path.name}: {e}")


def _send_email(email_cfg: dict, msg: MIMEMultipart):
    """通过 SMTP 发送邮件"""
    smtp_cfg = email_cfg.get('smtp', {})
    host = smtp_cfg.get('host', 'smtp.qq.com')
    port = smtp_cfg.get('port', 465)
    use_ssl = smtp_cfg.get('use_ssl', True)

    sender = email_cfg['sender']
    password = email_cfg['password']
    recipients = email_cfg['recipients']

    if use_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=context) as server:
            server.login(sender, password)
            server.sendmail(sender, recipients, msg.as_string())
    else:
        with smtplib.SMTP(host, port) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(sender, password)
            server.sendmail(sender, recipients, msg.as_string())


def start():
    """服务入口：扫描文件夹并发送邮件"""
    email_cfg = _load_email_config()

    # 校验必填字段
    required = ['sender', 'password', 'recipients', 'content_dir']
    for field in required:
        if not email_cfg.get(field):
            log.error(f"[daily_email] 缺少必填配置: email.{field}")
            return

    content_dir = email_cfg['content_dir']
    files = _scan_files(content_dir)

    if not files:
        log.info(f"[daily_email] 目录 {content_dir} 下没有文件，跳过发送")
        return

    log.info(f"[daily_email] 扫描到 {len(files)} 个文件，准备发送邮件")

    msg = _build_message(email_cfg, files)

    try:
        _send_email(email_cfg, msg)
        recipients_str = ', '.join(email_cfg['recipients'])
        log.info(f"[daily_email] 邮件发送成功 -> {recipients_str} ({len(files)} 个附件)")
    except smtplib.SMTPAuthenticationError:
        log.error("[daily_email] SMTP 认证失败，请检查邮箱账号和授权码")
    except smtplib.SMTPException as e:
        log.error(f"[daily_email] 邮件发送失败: {e}")
    except Exception as e:
        log.error(f"[daily_email] 发送异常: {e}")
