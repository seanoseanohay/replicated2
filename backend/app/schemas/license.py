from pydantic import BaseModel


class LicenseStatusRead(BaseModel):
    valid: bool
    license_type: str | None
    customer_name: str | None
    expires_at: str | None
    entitlements: dict[str, object]
