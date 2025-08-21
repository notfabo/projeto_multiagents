# schemas.py (adições e ajustes)
import uuid
import operator
from pydantic import BaseModel, Field
from typing import List, TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from datetime import datetime

# --- Schemas de Requisição (Request) ---

class UseCaseRequest(BaseModel):
    description: str = Field(..., examples=["Quero um chatbot para agendamento em uma barbearia."])

class ConversationRequest(BaseModel):
    user_input: str

# --- Schemas de Definição Interna ---

class ProposedAgent(BaseModel):
    role: str = Field(..., examples=["Agente de Agendamento"])
    responsibilities: str = Field(..., examples=["Coletar nome, serviço desejado, data e hora."])

class WorkflowResponse(BaseModel):
    # Este schema continua sendo usado para o parser da LLM
    proposed_agents: List[ProposedAgent]

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]

# --- Schemas de Resposta (Response) para o Banco de Dados ---
# Estes schemas definem como os dados do banco serão retornados na API

class AgentDefinitionDB(BaseModel):
    id: int
    role: str
    responsibilities: str

    class Config:
        from_attributes = True # Antigo orm_mode = True

class UseCaseDB(BaseModel):
    id: int
    description: str
    agents: List[AgentDefinitionDB] = []

    class Config:
        from_attributes = True

class UseCaseWithAgents(BaseModel):
    id: int
    description: str
    agents: List[AgentDefinitionDB] = []

    class Config:
        from_attributes = True
        
class MessageDB(BaseModel):
    id: int
    sender_role: str
    content: str
    timestamp: datetime

    class Config:
        from_attributes = True

class ConversationDB(BaseModel):
    id: int
    start_time: datetime
    messages: List[MessageDB] = []

    class Config:
        from_attributes = True

class UseCaseDetails(UseCaseWithAgents):
    conversations: List[ConversationDB] = []

    class Config:
        from_attributes = True

class ConversationResponse(BaseModel):
    conversation_id: int
    final_response: str