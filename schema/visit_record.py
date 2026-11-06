"""Visit record schema.

Two layers:
- `VisitExtraction`: what Claude extracts from the KAM's (anonymised) dictation.
  Sent to the API as the structured-output schema.
- `VisitRecord`: the full CRM-ready record = app metadata (visit id, date, account,
  segment, role) chosen in the UI + the extraction. Never filled in by the model.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Canal = Literal["presencial", "remoto", "telefónico"]
Cumplido = Literal["si", "parcial", "no"]
TipoObjecion = Literal["cientifica", "acceso", "proceso", "organizativa", "otra"]
Responsable = Literal["KAM", "Medical", "Market Access", "Marketing"]
Area = Literal["Medical", "Market Access", "Marketing"]
Segmento = Literal["A", "B", "C"]
Rol = Literal[
    "psiquiatra adultos",
    "psiquiatra infantil",
    "neuropediatra",
    "jefe de servicio",
    "farmacia hospitalaria",
    "otro",
]


class ObjetivoSmart(BaseModel):
    especifico: bool = Field(description="El objetivo dice qué se quería conseguir de forma concreta.")
    medible: bool = Field(description="El objetivo tiene un resultado observable o cuantificable.")
    con_plazo: bool = Field(description="El objetivo incluye un plazo o fecha.")
    que_falta: list[str] = Field(
        description="Qué le falta al objetivo para ser SMART, en frases cortas. Vacío si es SMART."
    )


class Objecion(BaseModel):
    tipo: TipoObjecion
    texto: str


class Receptividad(BaseModel):
    valor_1_5: Optional[int] = Field(
        description="1 = nada receptivo, 5 = muy receptivo. null si la nota no da pistas."
    )
    motivo: Optional[str] = Field(description="En qué frase de la nota se basa el valor. null si valor es null.")


class Colaboracion(BaseModel):
    area: Area
    peticion: str


class Alerta(BaseModel):
    detectado: bool
    fragmento: str = Field(description="Copia literal del fragmento de la nota. Cadena vacía si no se detecta.")


class Alertas(BaseModel):
    posible_efecto_adverso: Alerta
    pregunta_fuera_ficha: Alerta
    solicitud_informacion_medica: Alerta


class AlertaRevisada(Alerta):
    """Alert after merging the LLM and the local rules. Never sent to the model."""

    fuente: list[Literal["IA", "reglas"]] = Field(default_factory=list)
    otros_fragmentos: list[str] = Field(default_factory=list)  # the rules' sentence, when it differs
    confirmado_por_kam: bool = False  # "He notificado a Farmacovigilancia" / "He derivado a Medical"


class AlertasRevisadas(BaseModel):
    posible_efecto_adverso: AlertaRevisada
    pregunta_fuera_ficha: AlertaRevisada
    solicitud_informacion_medica: AlertaRevisada


class Sustitucion(BaseModel):
    """What the anonymiser replaced. The original value is never stored."""

    tipo: str
    sustituto: str


class VisitExtraction(BaseModel):
    """Structured output requested from Claude."""

    parece_conversacion: bool = Field(
        description="true si el texto parece una conversación entre varias personas en lugar de un dictado de la KAM."
    )
    canal: Optional[Canal]
    objetivo_visita: Optional[str]
    objetivo_smart: Optional[ObjetivoSmart] = Field(description="null si no hay objetivo_visita.")
    objetivo_cumplido: Optional[Cumplido]
    temas_tratados: list[str]
    necesidades_detectadas: list[str]
    objeciones: list[Objecion]
    materiales_solicitados: list[str]
    siguiente_paso: Optional[str]
    fecha_seguimiento: Optional[str] = Field(description="YYYY-MM-DD o null.")
    fecha_seguimiento_expresion: Optional[str] = Field(
        description="Expresión literal de la nota sobre el plazo (p. ej. 'en tres semanas'). null si no hay."
    )
    responsable_siguiente_paso: Optional[Responsable]
    receptividad: Receptividad
    colaboracion_transversal: list[Colaboracion]
    alertas: Alertas
    campos_faltantes: list[str]
    resumen_crm: str = Field(description="Máximo 400 caracteres. Tono profesional, neutro, no promocional.")


class VisitRecord(BaseModel):
    """Full record shown for review and, after approval, exported to the CRM."""

    visita_id: str
    fecha: str
    cuenta_id: str
    segmento: Optional[Segmento]
    interlocutor_rol: Rol
    canal: Optional[Canal]
    objetivo_visita: Optional[str]
    objetivo_smart: Optional[ObjetivoSmart]
    objetivo_cumplido: Optional[Cumplido]
    temas_tratados: list[str]
    necesidades_detectadas: list[str]
    objeciones: list[Objecion]
    materiales_solicitados: list[str]
    siguiente_paso: Optional[str]
    fecha_seguimiento: Optional[str]
    fecha_seguimiento_expresion: Optional[str]
    responsable_siguiente_paso: Optional[Responsable]
    receptividad: Receptividad
    colaboracion_transversal: list[Colaboracion]
    alertas: AlertasRevisadas
    campos_faltantes: list[str]
    resumen_crm: str
    # Review metadata — never set by the model
    anonimizacion: list[Sustitucion] = Field(default_factory=list)
    avisos_validacion: list[str] = Field(default_factory=list)
    aprobado: bool = False
