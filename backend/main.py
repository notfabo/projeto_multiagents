import os
import uuid
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List, TypedDict, Annotated, Sequence
import operator

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

load_dotenv()

# --------------------------------------------------------------------------
# 1. CONFIGURAÇÃO DA API E DOCUMENTAÇÃO (SWAGGER)
# --------------------------------------------------------------------------
app = FastAPI(
    title="Plataforma de Multiagentes Dinâmicos",
    description="Uma API para criar e orquestrar equipes de agentes inteligentes com base em casos de uso.",
    version="0.1.0",
)

# --------------------------------------------------------------------------
# 2. DEFINIÇÃO DOS MODELOS DE DADOS (PYDANTIC)
# --------------------------------------------------------------------------
class UseCaseRequest(BaseModel):
    """Modelo para a requisição do usuário, contendo a descrição do caso de uso."""
    description: str = Field(
        ...,
        examples=["Quero criar um fluxo de ponta a ponta para a compra e venda de carros usados."],
        description="Descrição detalhada do problema ou fluxo que os agentes devem resolver."
    )

class ProposedAgent(BaseModel):
    """Modelo para descrever um agente sugerido."""
    role: str = Field(..., examples=["Agente Vendedor"], description="A especialidade ou 'cargo' do agente.")
    responsibilities: str = Field(..., examples=["Encontrar potenciais compradores, negociar preços e fechar a venda."], description="As principais tarefas deste agente.")

class WorkflowResponse(BaseModel):
    case_id: str = Field(default_factory=lambda: f"case_{uuid.uuid4().hex[:8]}")
    proposed_agents: List[ProposedAgent]

class ConversationRequest(BaseModel):
    case_id: str
    user_input: str

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next_agent: str

# --------------------------------------------------------------------------
# 3. CRIAÇÃO DO ENDPOINT INTELIGENTE
# --------------------------------------------------------------------------
llm = ChatOpenAI(model_name="gpt-4.1-nano", temperature=0.2)

parser = PydanticOutputParser(pydantic_object=WorkflowResponse)

prompt_template = """
Você é um arquiteto de sistemas de multiagentes. Sua tarefa é analisar a descrição de um caso de uso e decompor o problema em uma equipe de agentes especialistas.

Para cada agente, defina claramente seu "role" (cargo/especialidade) e suas "responsibilities" (responsabilidades).

Crie no máximo 3 agentes por caso.

O caso de uso fornecido pelo usuário é:
"{user_case_description}"

Gere um ID de caso único no formato 'case_'.

{format_instructions}
"""

prompt = ChatPromptTemplate.from_template(
    template=prompt_template, 
    partial_variables={"format_instructions": parser.get_format_instructions()}
    )

architect_chain = prompt | llm | parser

workflows_in_memory = {}

def create_agent_node(role: str, responsibilities: str):
    """Função que cria uma 'chain' para um agente especialista."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"Você é um {role}. Suas responsabilidades são: {responsibilities}. Execute sua tarefa com base na conversa atual. Responda de forma concisa e focada na sua função."),
        ("human", "{input}")
    ])
    return prompt | llm

def supervisor_router(state: AgentState):
    """O 'gerente' que decide qual agente atua a seguir."""
    print(f"--- Supervisor analisando o estado ---")
    # Pega o último nome de agente da lista de mensagens
    last_message_sender_role = state['messages'][-1].additional_kwargs.get("role", "user")

    # Se a última mensagem foi do usuário ou do próprio supervisor, inicia o ciclo
    if last_message_sender_role == "user" or last_message_sender_role == "supervisor":
        return state['next_agent']
    else: # Se um especialista acabou de falar, volta para o supervisor decidir
        return "supervisor"

@app.post("/create_workflow_from_case", response_model=WorkflowResponse)
async def create_workflow(request: UseCaseRequest):
    """
    Recebe a descrição de um caso de uso e retorna uma proposta de equipe de agentes especialistas.
    """
    print(f"Recebido caso de uso: {request.description}")

    response = await chain.ainvoke({"user_case_description": request.description})

    return response

@app.post("/design_workflow", response_model=WorkflowDesign)
async def design_workflow(request: UseCaseRequest):
    """
    Passo 1: Projeta a equipe de agentes com base no caso de uso.
    """
    print(f"Recebido caso de uso para design: {request.description}")
    
    workflow_design = await architect_chain.ainvoke({"user_case_description": request.description})
    
    # --- Montagem dinâmica do Grafo com LangGraph ---
    workflow = StateGraph(AgentState)
    
    # 1. Nó do Supervisor
    supervisor_chain = ChatPromptTemplate.from_messages([
        ("system", 
         """Você é um supervisor de uma equipe de agentes de IA. Dada a conversa a seguir, selecione o próximo agente para agir ou responda 'FINISH' se a tarefa estiver concluída.
         Agentes disponíveis: {agent_roles}"""),
        ("human", "{input}"),
    ]) | llm

    agent_roles = [agent.role for agent in workflow_design.proposed_agents]
    supervisor_node = supervisor_chain.with_config(
        {"run_name": "Supervisor"}
    ).with_retry(
        stop_after_attempt=3
    )

    workflow.add_node("supervisor", lambda state: {"messages": [AIMessage(content=supervisor_node.invoke({"agent_roles": ", ".join(agent_roles), "input": state['messages']}).content, additional_kwargs={"role": "supervisor"})]})

    # 2. Nós dos Agentes Especialistas
    for agent_spec in workflow_design.proposed_agents:
        agent_node = create_agent_node(agent_spec.role, agent_spec.responsibilities)
        workflow.add_node(agent_spec.role, lambda state, role=agent_spec.role: {"messages": [AIMessage(content=agent_node.invoke({"input": state['messages']}).content, additional_kwargs={"role": role})]})

    # 3. Conexões (Edges)
    for agent_role in agent_roles:
        workflow.add_edge(agent_role, "supervisor")
        
    workflow.add_conditional_edges(
        "supervisor",
        lambda state: state['messages'][-1].content, # Roteia com base no conteúdo da mensagem do supervisor
        {role: role for role in agent_roles} | {"FINISH": END}
    )
    
    workflow.set_entry_point("supervisor")
    
    # Compila o grafo e armazena em memória
    graph = workflow.compile()
    workflows_in_memory[workflow_design.case_id] = graph
    
    print(f"Workflow para o caso '{workflow_design.case_id}' criado e compilado.")
    return workflow_design


@app.post("/run_conversation")
async def run_conversation(request: ConversationRequest):
    """
    Passo 2: Executa uma conversa usando um workflow já projetado.
    """
    print(f"Iniciando conversa para o caso '{request.case_id}' com a entrada: '{request.user_input}'")
    
    graph = workflows_in_memory.get(request.case_id)
    if not graph:
        return {"error": "Workflow não encontrado. Por favor, crie o design primeiro."}

    initial_state = {
        "messages": [HumanMessage(content=request.user_input, additional_kwargs={"role": "user"})]
    }
    
    # O stream nos permite ver cada passo da conversa
    response_stream = graph.astream(initial_state)
    
    final_response = None
    async for step in response_stream:
        # A chave 'supervisor' conterá a resposta final mais provável
        if "supervisor" in step:
            final_response = step["supervisor"]
            print(f"--- Resposta Final --- \n {final_response}")

    return final_response