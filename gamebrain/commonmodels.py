from pydantic import BaseModel


class ConsoleUrl(BaseModel):
    id: str
    url: str
    name: str
