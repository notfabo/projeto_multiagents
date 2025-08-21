import { Routes } from '@angular/router';
import { HomeComponent } from './components/home/home.component';
import { UseCaseDetailComponent } from './components/use-case-detail/use-case-detail.component';

export const routes: Routes = [
  { path: '', component: HomeComponent },
  { path: 'use-case/:id', component: UseCaseDetailComponent },
  { path: '**', redirectTo: '' }
];
