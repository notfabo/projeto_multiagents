import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
from dotenv import load_dotenv

# Importe seus modelos e schemas
import models.models as models
import schemas as schemas
from database.setup_database import SessionLocal, engine

# Importações do LangChain/LangGraph
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, END

load_dotenv()

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Plataforma de Multiagentes Dinâmicos",
    description="Uma API para criar e orquestrar equipes de agentes inteligentes com base em casos de uso.",
    version="0.2.0",
)

origins = [
    "http://localhost:4200",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Configuração do LangChain (Arquiteto de Agentes) ---
llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.2) # Modelo mais recente e econômico
parser = PydanticOutputParser(pydantic_object=schemas.WorkflowResponse)

prompt_template = """
Você é um arquiteto de sistemas de multiagentes. Sua tarefa é analisar a descrição de um caso de uso e decompor o problema em uma equipe de agentes especialistas.
Para cada agente, defina claramente seu "role" (cargo/especialidade) e suas "responsibilities" (responsabilidades).
O último agente deve ser um 'Finalizador' ou 'Consolidador' que entrega a resposta final ao usuário.
O caso de uso fornecido pelo usuário é:
"{user_case_description}"
{format_instructions}
"""

prompt = ChatPromptTemplate.from_template(
    template=prompt_template,
    partial_variables={"format_instructions": parser.get_format_instructions()}
)

architect_chain = prompt | llm | parser

# --- Funções do Grafo (Reutilizáveis) ---
def create_agent_node(role: str, responsibilities: str):
    """Função que cria uma 'chain' para um agente especialista."""
    agent_prompt = ChatPromptTemplate.from_messages([
        ("system", f"Você é um {role}. Suas responsabilidades são: {responsibilities}. Com base no histórico da conversa, execute sua tarefa. Responda de forma concisa e focada na sua função, passando o controle para o próximo agente ou finalizando a tarefa."),
        ("placeholder", "{messages}")
    ])
    return agent_prompt | llm

def create_supervisor_chain(agent_roles: List[str]):
    """Cria a 'chain' do supervisor que decide o próximo passo."""
    options = agent_roles + ["FINISH"]
    
    supervisor_prompt = ChatPromptTemplate.from_messages([
        ("system",
         """Você é um supervisor de uma equipe de agentes de IA. Sua tarefa é analisar a conversa e decidir qual agente deve agir em seguida.
         
         Agentes disponíveis: {agent_roles}
         
         Com base na última mensagem, escolha o próximo passo. A tarefa está concluída e a resposta final foi dada? Se sim, responda com a palavra 'FINISH'.
         Caso contrário, responda com o nome exato de um dos agentes da lista.

         Sua resposta DEVE SER ESTRITAMENTE UMA das seguintes opções: {options}
         NÃO adicione nenhuma outra palavra, pontuação ou explicação.
         
         Exemplo:
         - Se o 'Agente de Viagens' deve agir, sua resposta deve ser:
         Agente de Viagens
         
         - Se a tarefa acabou, sua resposta deve ser:
         FINISH
         """),
        ("placeholder", "{messages}"),
    ])
    
    return supervisor_prompt.partial(options=options) | llm

# --- Endpoints da API ---

@app.post("/use_cases/", response_model=schemas.UseCaseDB)
async def create_use_case(request: schemas.UseCaseRequest, db: Session = Depends(get_db)):
    """
    Passo 1: Recebe um caso de uso, projeta a equipe de agentes com a LLM
    e salva o resultado no banco de dados.
    """
    print(f"Recebido caso de uso para design: {request.description}")
    
    # 1. Usar a LLM para projetar os agentes
    try:
        workflow_design = await architect_chain.ainvoke({"user_case_description": request.description})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao invocar a LLM: {e}")

    # 2. Criar e salvar o caso de uso no banco
    db_use_case = models.UseCase(description=request.description)
    db.add(db_use_case)
    db.commit()
    db.refresh(db_use_case)

    # 3. Salvar as definições dos agentes vinculadas ao caso de uso
    for agent_spec in workflow_design.proposed_agents:
        db_agent = models.AgentDefinition(
            use_case_id=db_use_case.id,
            role=agent_spec.role,
            responsibilities=agent_spec.responsibilities
        )
        db.add(db_agent)
    
    db.commit()
    db.refresh(db_use_case) # Refresh para carregar os agentes recém-criados
    
    return db_use_case

@app.post("/use_cases/{case_id}/conversation/", response_model=schemas.ConversationResponse)
async def run_conversation(case_id: int, request: schemas.ConversationRequest, db: Session = Depends(get_db)):
    """
    Passo 2: Inicia uma conversa para um caso de uso existente.
    Ele reconstrói o grafo dinamicamente a partir das definições do banco.
    """
    print(f"Iniciando conversa para o caso ID '{case_id}' com a entrada: '{request.user_input}'")

    # 1. Buscar o caso de uso e seus agentes no banco
    use_case = db.query(models.UseCase).filter(models.UseCase.id == case_id).first()
    if not use_case or not use_case.agents:
        raise HTTPException(status_code=404, detail="Caso de uso ou agentes não encontrados.")

    # 2. Reconstruir o grafo dinamicamente
    workflow = StateGraph(schemas.AgentState)
    agent_roles = [agent.role for agent in use_case.agents]
    
    # Adicionar nós dos agentes
    for agent in use_case.agents:
        agent_node = create_agent_node(agent.role, agent.responsibilities)
        workflow.add_node(agent.role, lambda state, role=agent.role: {"messages": [agent_node.invoke({"messages": state['messages']})]})

    # Adicionar nó do supervisor
    supervisor_chain = create_supervisor_chain(agent_roles)
    workflow.add_node("supervisor", lambda state: {"messages": [supervisor_chain.invoke({"agent_roles": ", ".join(agent_roles), "messages": state['messages']})]})

    # Definir as arestas (como os nós se conectam)
    for agent_role in agent_roles:
        workflow.add_edge(agent_role, "supervisor")

    # O supervisor decide para onde ir
    conditional_map = {role: role for role in agent_roles}
    conditional_map["FINISH"] = END
    workflow.add_conditional_edges("supervisor", lambda state: state['messages'][-1].content.strip(), conditional_map)
    
    workflow.set_entry_point("supervisor")
    graph = workflow.compile()
    
    # 3. Salvar o início da conversa no banco
    db_conversation = models.Conversation(use_case_id=case_id)
    db.add(db_conversation)
    db.commit()
    db.refresh(db_conversation)

    initial_message = HumanMessage(content=request.user_input)
    db_message = models.Message(conversation_id=db_conversation.id, sender_role="user", content=initial_message.content)
    db.add(db_message)
    db.commit()

    # 4. Executar a conversa
    final_state = None
    async for state in graph.astream({"messages": [initial_message]}):
        # A cada passo, você pode opcionalmente salvar as mensagens dos agentes no DB aqui
        print(f"--- Estado do Grafo ---\n{state}\n")
        final_state = state

    final_messages = final_state['messages']
    
    # Salvar as mensagens geradas pelos agentes no DB
    for msg in final_messages[1:]: # Ignora a mensagem inicial do usuário que já foi salva
        if isinstance(msg, AIMessage):
            db_agent_message = models.Message(
                conversation_id=db_conversation.id,
                sender_role=msg.name or "agent", # O nome do nó pode ser passado aqui
                content=msg.content
            )
            db.add(db_agent_message)
    db.commit()
    
    return {"conversation_id": db_conversation.id, "final_response": final_messages[-1].content}


# --- ENDPOINTS ADICIONAIS ---

@app.get("/use_cases/", response_model=List[schemas.UseCaseWithAgents])
def get_all_use_cases(db: Session = Depends(get_db)):
    """
    Retorna uma lista de todos os casos de uso criados e seus respectivos agentes.
    """
    use_cases = db.query(models.UseCase).all()
    return use_cases

@app.get("/use_cases/{case_id}/", response_model=schemas.UseCaseDetails)
def get_use_case_details(case_id: int, db: Session = Depends(get_db)):
    """
    Retorna todos os dados de um caso específico, incluindo agentes e histórico de conversas.
    """
    use_case = db.query(models.UseCase).filter(models.UseCase.id == case_id).first()
    if not use_case:
        raise HTTPException(status_code=404, detail="Caso de uso não encontrado.")
    return use_case