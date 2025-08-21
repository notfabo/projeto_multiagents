export interface AgentDefinition {
  id: number;
  role: string;
  responsibilities: string;
}

export interface UseCase {
  id: number;
  description: string;
  agents: AgentDefinition[];
}

export interface Message {
  id: number;
  sender_role: string;
  content: string;
  timestamp: string;
}

export interface Conversation {
  id: number;
  start_time: string;
  messages: Message[];
}

export interface UseCaseDetails extends UseCase {
  conversations: Conversation[];
}

export interface CreateUseCaseRequest {
  description: string;
}

export interface ConversationRequest {
  user_input: string;
}

export interface ConversationResponse {
  conversation_id: number;
  final_response: string;
}
