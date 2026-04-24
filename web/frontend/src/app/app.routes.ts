import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./pages/home/home.component').then((m) => m.HomeComponent),
  },
  {
    path: 'analyze',
    loadComponent: () =>
      import('./pages/analyze/analyze.component').then((m) => m.AnalyzeComponent),
  },
  {
    path: 'results',
    loadComponent: () =>
      import('./pages/results/results.component').then((m) => m.ResultsComponent),
  },
  {
    path: 'history',
    loadComponent: () =>
      import('./pages/history/history.component').then((m) => m.HistoryComponent),
  },
  {
    path: 'camera',
    loadComponent: () =>
      import('./pages/camera/camera.component').then((m) => m.CameraComponent),
  },
  {
    path: '**',
    redirectTo: '',
  },
];
