"""
Email Service - Send emails using AWS SES
"""

import boto3
import logging
from botocore.exceptions import ClientError
from typing import Optional

logger = logging.getLogger(__name__)

# AWS Configuration
AWS_REGION = "ap-southeast-1"
SENDER_EMAIL = "no-reply@arc-chatbot.com"  # Must be verified in SES


class EmailService:
    """Service for sending emails via AWS SES."""

    def __init__(self, region_name: str = AWS_REGION, sender_email: str = SENDER_EMAIL):
        self.region_name = region_name
        self.sender_email = sender_email
        self._client = boto3.client("ses", region_name=region_name)

    def send_welcome_email(
        self,
        to_email: str,
        display_name: str,
    ) -> bool:
        """
        Send welcome email after successful registration.

        Args:
            to_email: Recipient email address
            display_name: User's display name

        Returns:
            True if email sent successfully, False otherwise
        """
        subject = "🎉 Chào mừng bạn đến với ARC-Chatbot!"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #3b82f6, #10b981); padding: 30px; border-radius: 12px 12px 0 0; text-align: center; }}
                .header h1 {{ color: white; margin: 0; font-size: 24px; }}
                .content {{ background: #f8fafc; padding: 30px; border-radius: 0 0 12px 12px; }}
                .highlight {{ background: #e0f2fe; padding: 15px; border-radius: 8px; margin: 20px 0; }}
                .footer {{ text-align: center; margin-top: 20px; color: #64748b; font-size: 12px; }}
                .btn {{ display: inline-block; background: #3b82f6; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; margin-top: 15px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎓 ARC-Chatbot</h1>
                    <p style="color: #e0f2fe; margin: 5px 0 0 0;">Research Assistant</p>
                </div>
                <div class="content">
                    <h2>Xin chào {display_name}! 👋</h2>
                    
                    <p>Chúc mừng bạn đã đăng ký thành công tài khoản <strong>Researcher</strong> trên hệ thống ARC-Chatbot - Trợ lý nghiên cứu học thuật thông minh.</p>
                    
                    <div class="highlight">
                        <strong>📧 Tài khoản của bạn:</strong><br>
                        Email: {to_email}<br>
                        Tên hiển thị: {display_name}
                    </div>
                    
                    <p><strong>Với ARC-Chatbot, bạn có thể:</strong></p>
                    <ul>
                        <li>🔍 Tìm kiếm thông tin từ các tài liệu nghiên cứu</li>
                        <li>💬 Đặt câu hỏi và nhận câu trả lời có trích dẫn nguồn</li>
                        <li>📚 Quản lý và upload tài liệu PDF</li>
                        <li>📊 Xem lịch sử hội thoại</li>
                    </ul>
                    
                    <p style="text-align: center;">
                        <a href="https://arc-chatbot.com/login" class="btn">Đăng nhập ngay</a>
                    </p>
                    
                    <p style="margin-top: 25px;">Chúc bạn học tập và nghiên cứu hiệu quả! 📖✨</p>
                    
                    <p>Trân trọng,<br><strong>Đội ngũ ARC-Chatbot</strong></p>
                </div>
                <div class="footer">
                    <p>© 2024 ARC-Chatbot. All rights reserved.</p>
                    <p>Email này được gửi tự động, vui lòng không trả lời.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_body = f"""
        Xin chào {display_name}!

        Chúc mừng bạn đã đăng ký thành công tài khoản Researcher trên hệ thống ARC-Chatbot.

        Tài khoản của bạn:
        - Email: {to_email}
        - Tên hiển thị: {display_name}

        Với ARC-Chatbot, bạn có thể:
        - Tìm kiếm thông tin từ các tài liệu nghiên cứu
        - Đặt câu hỏi và nhận câu trả lời có trích dẫn nguồn
        - Quản lý và upload tài liệu PDF
        - Xem lịch sử hội thoại

        Chúc bạn học tập và nghiên cứu hiệu quả!

        Trân trọng,
        Đội ngũ ARC-Chatbot
        """

        try:
            response = self._client.send_email(
                Source=self.sender_email,
                Destination={"ToAddresses": [to_email]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": text_body, "Charset": "UTF-8"},
                        "Html": {"Data": html_body, "Charset": "UTF-8"},
                    },
                },
            )
            logger.info(f"Welcome email sent to {to_email}, MessageId: {response['MessageId']}")
            return True

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"Failed to send welcome email to {to_email}: {error_code} - {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email to {to_email}: {e}")
            return False


# Singleton instance
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Get or create EmailService instance."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
