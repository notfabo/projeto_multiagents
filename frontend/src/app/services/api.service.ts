import { Inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  constructor(
    private http: HttpClient,
    @Inject('API_URL') private apiUrl: string
  ) {}


  // Use Case Endpoints
  createUseCase(description: string) {
    return this.http.post(`${this.apiUrl}/use_cases/`, { description });
  }

  getUseCases() {
    return this.http.get(`${this.apiUrl}/use_cases/`);
  }

  getUseCaseDetails(useCaseId: number) {
    return this.http.get(`${this.apiUrl}/use_cases/${useCaseId}`);
  }

  // Conversation Endpoints
  startConversation(useCaseId: number, userInput: string) {
    return this.http.post(`${this.apiUrl}/use_cases/${useCaseId}/conversation`, {
      user_input: userInput
    });
  }

  sendMessage(useCaseId: number, conversationId: number, message: string) {
    return this.http.post(`${this.apiUrl}/use_cases/${useCaseId}/conversation/${conversationId}`, {
      user_input: message
    });
  }
}
