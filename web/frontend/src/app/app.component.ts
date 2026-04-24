import { Component } from '@angular/core';
import { RouterOutlet, RouterLink } from '@angular/router';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink],
  template: `
    <nav class="bg-white border-b border-gray-200 sticky top-0 z-10">
      <div class="max-w-5xl mx-auto px-4 sm:px-6 flex items-center justify-between h-16">
        <a routerLink="/" class="text-xl font-bold text-blue-600 tracking-tight">FormCheck</a>
        <div class="flex gap-2">
          <a routerLink="/history" class="text-sm text-gray-600 hover:text-gray-900 px-3 py-2">History</a>
          <a routerLink="/camera" class="btn-secondary text-sm py-2 px-4">Live camera</a>
          <a routerLink="/analyze" class="btn-primary text-sm py-2 px-4">Upload video</a>
        </div>
      </div>
    </nav>
    <main>
      <router-outlet />
    </main>
    <footer class="mt-24 border-t border-gray-100 py-8 text-center text-sm text-gray-400">
      FormCheck &mdash; upload a video, get your rep count and form quality score.
    </footer>
  `,
})
export class AppComponent {}
