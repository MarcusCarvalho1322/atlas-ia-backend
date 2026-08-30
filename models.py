"""
Modelo de dados do caso ATLAS-IA.

Espelha exatamente a estrutura que hoje vive só no localStorage do
navegador (ver App.jsx: `salvarCaso`/`carregarCaso`), para que a migração
do front-end seja só trocar "onde" o caso é salvo — nenhum campo muda de
nome ou de formato.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, JSON, Integer
from db import Base


def _new_id() -> str:
    # Mesmo formato curto que o front-end já gera hoje com Date.now().toString(36)
    return uuid.uuid4().hex[:12]


class Caso(Base):
    __tablename__ = "casos"

    id = Column(String, primary_key=True, default=_new_id)
    form_data = Column(JSON, nullable=False)      # espelha formData do App.jsx
    audit_result = Column(JSON, nullable=True)    # espelha auditResult do App.jsx (pode ser null)
    geo_verificacoes = Column(JSON, nullable=True)  # histórico de checagens de satélite feitas para este caso
    saved_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                         onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "formData": self.form_data,
            "auditResult": self.audit_result,
            "geoVerificacoes": self.geo_verificacoes or [],
            "savedAt": self.saved_at.isoformat() if self.saved_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
