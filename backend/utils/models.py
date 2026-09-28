from pydantic import BaseModel, Field





class UnitReceiverResponse(BaseModel):
    receiver_meter_no: int = Field(...)
    sender_meter_no: int = Field(...)
    units: int = Field(...)
    

class TokenValidator(BaseModel):
    meterNo: int = Field(...)
    token: int = Field(...)