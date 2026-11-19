from dataclasses import dataclass
OTP_TTL_SECONDS, RESEND_COOLDOWN_SECONDS, MAX_ATTEMPTS, SESSION_TTL_SECONDS = 120, 30, 3, 1800
@dataclass(frozen=True)
class VerifyResult: status: str; token: str | None = None
def requestOtp(phone): raise NotImplementedError("TODO(1) not implemented yet")
def verifyOtp(phone, code): raise NotImplementedError("TODO(2) not implemented yet")
def session(token):
    if not token or not token.strip(): return None
    raise NotImplementedError("TODO(3) not implemented yet")
def logout(token): raise NotImplementedError("TODO(4) not implemented yet")
