from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class UseCase(Base):
    __tablename__ = "use_cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    description = Column(String(255), nullable=False)

    # Relacionamentos
    agents = relationship("AgentDefinition", back_populates="use_case", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="use_case", cascade="all, delete-orphan")


class AgentDefinition(Base):
    __tablename__ = "agent_definitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    use_case_id = Column(Integer, ForeignKey("use_cases.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(100), nullable=False)
    responsibilities = Column(Text, nullable=True)

    # Relacionamento inverso
    use_case = relationship("UseCase", back_populates="agents")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    use_case_id = Column(Integer, ForeignKey("use_cases.id", ondelete="CASCADE"), nullable=False)
    start_time = Column(DateTime, default=datetime.utcnow)

    # Relacionamentos
    use_case = relationship("UseCase", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    sender_role = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relacionamento inverso
    conversation = relationship("Conversation", back_populates="messages")
