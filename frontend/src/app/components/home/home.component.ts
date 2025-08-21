import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { finalize } from 'rxjs/operators';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { ApiService } from '../../services/api.service';
import { UseCase } from '../../models/use-case.model';
import { TruncatePipe } from '../../pipes/truncate.pipe';

@Component({
  selector: 'app-home',
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.scss'],
  standalone: true,
  imports: [CommonModule, FormsModule, TruncatePipe]
})
export class HomeComponent implements OnInit {
  useCases: UseCase[] = [];
  isLoading = true;
  showCreateForm = false;
  newUseCaseDescription = '';
  isCreating = false;

  constructor(
    private apiService: ApiService,
    private router: Router
  ) {}

  ngOnInit() {
    this.loadUseCases();
  }

  loadUseCases() {
    this.isLoading = true;
    this.apiService.getUseCases()
      .pipe(
        finalize(() => this.isLoading = false)
      )
      .subscribe({
        next: (response: any) => {
          this.useCases = response as UseCase[];
        },
        error: (error) => {
          console.error('Error loading use cases:', error);
          // You could add a user-friendly error message here
        }
      });
  }

  createUseCase() {
    if (!this.newUseCaseDescription.trim()) return;
    
    this.isCreating = true;
    this.apiService.createUseCase(this.newUseCaseDescription)
      .pipe(
        finalize(() => this.isCreating = false)
      )
      .subscribe({
        next: (response: any) => {
          this.useCases.unshift(response);
          this.newUseCaseDescription = '';
          this.showCreateForm = false;
          // Navigate to the new use case
          this.router.navigate(['/use-case', response.id]);
        },
        error: (error) => {
          console.error('Error creating use case:', error);
          // You could add a user-friendly error message here
        }
      });
  }

  viewUseCase(useCaseId: number) {
    this.router.navigate(['/use-case', useCaseId]);
  }
}
