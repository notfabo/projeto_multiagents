import { Component, OnDestroy, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { finalize } from 'rxjs/operators';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { ApiService } from '../../services/api.service';
import { UseCase, UseCaseDetails, AgentDefinition, Conversation, Message } from '../../models/use-case.model';
import { TruncatePipe } from '../../pipes/truncate.pipe';

@Component({
  selector: 'app-use-case-detail',
  templateUrl: './use-case-detail.component.html',
  styleUrls: ['./use-case-detail.component.scss'],
  standalone: true,
  imports: [CommonModule, FormsModule, TruncatePipe]
})
export class UseCaseDetailComponent implements OnInit, OnDestroy {
  useCaseId!: number;
  useCase: UseCaseDetails | null = null;
  activeTab: 'agents' | 'chat' = 'chat';
  isLoading = true;
  error: string | null = null;
  
  // Chat properties
  messages: Message[] = [];
  newMessage = '';
  isSending = false;
  activeConversationId: number | null = null;
  
  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private apiService: ApiService
  ) {}

  private routeSub: any;

  ngOnInit() {
    this.routeSub = this.route.params.subscribe(params => {
      this.useCaseId = +params['id'];
      this.loadUseCaseDetails();
    });
  }

  ngOnDestroy() {
    if (this.routeSub) {
      this.routeSub.unsubscribe();
    }
  }

  loadUseCaseDetails() {
    this.isLoading = true;
    this.error = null;
    
    this.apiService.getUseCaseDetails(this.useCaseId)
      .pipe(
        finalize(() => this.isLoading = false)
      )
      .subscribe({
        next: (response: any) => {
          this.useCase = response as UseCaseDetails;
          
          // If there are conversations, load the most recent one
          if (this.useCase?.conversations && this.useCase.conversations.length > 0) {
            const latestConversation = this.useCase.conversations.reduce((latest: Conversation, current: Conversation) => 
              new Date(current.start_time) > new Date(latest.start_time) ? current : latest
            );
            this.loadConversation(latestConversation.id);
          }
        },
        error: (error) => {
          console.error('Error loading use case details:', error);
          this.error = 'Failed to load use case details. Please try again later.';
        }
      });
  }

  loadConversation(conversationId: number) {
    this.activeConversationId = conversationId;
    const conversation = this.useCase?.conversations?.find((c: Conversation) => c.id === conversationId);
    if (conversation) {
      this.messages = [...conversation.messages];
    }
  }

  startNewConversation() {
    this.activeConversationId = null;
    this.messages = [];
  }

  sendMessage() {
    if (!this.newMessage.trim() || this.isSending) return;
    
    const userMessage: Message = {
      id: Date.now(), // Temporary ID
      sender_role: 'user',
      content: this.newMessage,
      timestamp: new Date().toISOString()
    };
    
    this.messages = [...this.messages, userMessage];
    const messageContent = this.newMessage;
    this.newMessage = '';
    this.isSending = true;
    this.error = null;
    
    const request$ = this.activeConversationId
      ? this.apiService.sendMessage(this.useCaseId, this.activeConversationId, messageContent)
      : this.apiService.startConversation(this.useCaseId, messageContent);
    
    request$
      .pipe(
        finalize(() => this.isSending = false)
      )
      .subscribe({
        next: (response: any) => {
          const agentResponse: Message = {
            id: Date.now(),
            sender_role: 'assistant',
            content: response.final_response,
            timestamp: new Date().toISOString()
          };
          
          this.messages = [...this.messages, agentResponse];
          
          // If this was a new conversation, update the active conversation ID
          if (!this.activeConversationId && response.conversation_id) {
            this.activeConversationId = response.conversation_id;
            // Reload use case details to get the updated conversation list
            this.loadUseCaseDetails();
          } else {
            // Just scroll to bottom if not reloading the page
            this.scrollToBottom();
          }
        },
        error: (error) => {
          console.error('Error sending message:', error);
          this.error = 'Failed to send message. Please try again.';
          this.scrollToBottom();
        }
      });
  }

  goBack() {
    this.router.navigate(['/']);
  }
  
  private scrollToBottom() {
    setTimeout(() => {
      const chatContainer = document.querySelector('.chat-messages');
      if (chatContainer) {
        chatContainer.scrollTop = chatContainer.scrollHeight;
      }
    }, 100);
  }
}
