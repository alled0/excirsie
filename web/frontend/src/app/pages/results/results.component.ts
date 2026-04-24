import { Component, OnInit } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { NgFor, NgIf, NgClass, DecimalPipe, PercentPipe } from '@angular/common';

import { ApiService } from '../../services/api.service';
import { AnalysisResult } from '../../models/analysis.model';

@Component({
  selector: 'app-results',
  standalone: true,
  imports: [RouterLink, FormsModule, NgFor, NgIf, NgClass, DecimalPipe, PercentPipe],
  templateUrl: './results.component.html',
})
export class ResultsComponent implements OnInit {
  result: AnalysisResult | null = null;

  // Feedback form state
  rating = 0;
  wasAccurate = true;
  comment = '';
  feedbackSubmitted = false;
  feedbackError = '';

  constructor(private router: Router, private api: ApiService) {}

  ngOnInit(): void {
    const nav = this.router.getCurrentNavigation();
    const state = nav?.extras?.state as { result?: AnalysisResult } | undefined;

    if (state?.result) {
      this.result = state.result;
    } else {
      // Landed here without going through the upload flow
      this.router.navigateByUrl('/analyze');
    }
  }

  get qualityLabel(): string {
    const q = this.result?.signalQuality ?? 0;
    if (q >= 0.85) return 'Excellent';
    if (q >= 0.65) return 'Good';
    if (q >= 0.45) return 'Fair';
    return 'Poor';
  }

  get qualityColor(): string {
    const q = this.result?.signalQuality ?? 0;
    if (q >= 0.85) return 'text-green-600';
    if (q >= 0.65) return 'text-blue-600';
    if (q >= 0.45) return 'text-yellow-600';
    return 'text-red-600';
  }

  get stars(): number[] {
    return [1, 2, 3, 4, 5];
  }

  setRating(n: number): void {
    this.rating = n;
  }

  submitFeedback(): void {
    if (!this.result || this.rating === 0) return;

    this.api.submitFeedback({
      exerciseKey:      this.result.exerciseKey,
      rating:           this.rating,
      repCountAccurate: this.wasAccurate,
      comment:          this.comment,
    }).subscribe({
      next: () => {
        this.feedbackSubmitted = true;
      },
      error: () => {
        this.feedbackError = 'Could not save your feedback. Please try again.';
      },
    });
  }
}
