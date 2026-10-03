from typing import Annotated

from pydantic import BaseModel, Field

Label = Annotated[int, Field(ge=0, le=1)]


class DatasetRow(BaseModel):
    text: str
    label: Label
    category: str
