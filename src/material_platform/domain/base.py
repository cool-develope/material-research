from pydantic import BaseModel, ConfigDict


class Contract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )
