from sqlalchemy import Column, Integer, String, Boolean, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class ModelCatalog(Base):
    __tablename__ = "model_catalog"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)          # human-friendly name
    model_id = Column(String(256), nullable=False, unique=True)  # openrouter model string
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<ModelCatalog id={self.id} name={self.name} model_id={self.model_id}>"
