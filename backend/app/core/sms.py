import logging
from typing import Optional
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from app.core.config import settings

logger = logging.getLogger(__name__)

class SMSClient:
    def __init__(self):
        self.enabled = all([
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN,
            settings.TWILIO_PHONE_NUMBER
        ])
        if self.enabled:
            self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        else:
            logger.warning("Twilio credentials not fully configured. SMS will be logged to console only.")

    async def send_otp(self, phone: str, otp: str) -> bool:
        message_body = f"Your EduTrack verification code is: {otp}. Valid for 10 minutes."
        
        if not self.enabled:
            if settings.ENABLE_MOCK_SMS_OUTPUT:
                print(f"\n[MOCK SMS] To: {phone} | Body: {message_body}\n")
            else:
                logger.info("Mock SMS delivery simulated for %s", phone)
            return True

        try:
            self.client.messages.create(
                body=message_body,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=phone
            )
            return True
        except TwilioRestException as e:
            logger.error(f"Twilio error sending SMS to {phone}: {e}")
            return False

sms_client = SMSClient()
