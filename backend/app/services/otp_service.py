import os
import random
import logging
from typing import Optional
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)

class OTPService:
    """
    Handles generation, storage, and real SMS delivery of OTPs via Twilio.
    """
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = os.getenv("TWILIO_FROM_NUMBER")
        
        if self.account_sid and self.auth_token:
            self.client = Client(self.account_sid, self.auth_token)
        else:
            self.client = None
            logger.warning("Twilio credentials not found. OTP delivery will be mocked.")

    def generate_otp(self) -> str:
        """Generate a 6-digit numeric OTP."""
        return str(random.randint(100000, 999999))

    async def send_otp(self, phone_number: str, otp: str) -> bool:
        """
        Send OTP via Twilio SMS.
        Returns True if successful, False otherwise.
        """
        if not self.client:
            logger.info(f"[MOCK OTP] Sending {otp} to {phone_number}")
            return True
            
        try:
            message = self.client.messages.create(
                body=f"Your EduTrack verification code is: {otp}. Valid for 5 minutes.",
                from_=self.from_number,
                to=phone_number
            )
            logger.info(f"OTP sent to {phone_number}: SID {message.sid}")
            return True
        except TwilioRestException as e:
            logger.error(f"Failed to send OTP via Twilio: {e}")
            return False

    async def verify_otp(self, stored_otp: str, user_otp: str) -> bool:
        """Simple equality check for verification."""
        if not stored_otp or not user_otp:
            return False
        return stored_otp == user_otp

otp_service = OTPService()
