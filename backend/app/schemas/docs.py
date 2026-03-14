import uuid
from pydantic import BaseModel
from typing import Optional, List

class DocResponse(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID
    file_path: str
    function_name: Optional[str] = None
    class_name: Optional[str] = None
    docstring: Optional[str] = None

    class Config:
        from_attributes = True

class FunctionResponse(BaseModel):
    id: uuid.UUID
    function_name: str
    file_path: str
    class_name: Optional[str] = None
    docstring: Optional[str] = None
    parameters: Optional[List[str]] = None
    return_type: Optional[str] = None
    complexity_score: Optional[float] = None
    lines_of_code: Optional[int] = None
    handles_pii: bool = False
    is_entry_point: bool = False
    is_protected: bool = False
    
    class Config:
        from_attributes = True
