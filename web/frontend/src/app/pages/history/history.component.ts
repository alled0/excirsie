import { Component, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { NgFor, NgIf, NgClass, DatePipe, DecimalPipe, PercentPipe } from '@angular/common';

import { ApiService, HistoryRecord } from '../../services/api.service';

@Component({
  selector: 'app-history',
  standalone: true,
  imports: [RouterLink, NgFor, NgIf, NgClass, DatePipe, DecimalPipe, PercentPipe],
  templateUrl: './history.component.html',
})
export class HistoryComponent implements OnInit {
  records: HistoryRecord[] = [];
  loading = true;
  error = false;

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.api.getHistory().subscribe({
      next: (rows) => {
        this.records = rows;
        this.loading = false;
      },
      error: () => {
        this.error = true;
        this.loading = false;
      },
    });
  }

  qualityLabel(q: number | null): string {
    if (q === null || q === undefined) return '—';
    if (q >= 0.85) return 'Excellent';
    if (q >= 0.65) return 'Good';
    if (q >= 0.45) return 'Fair';
    return 'Poor';
  }

  qualityClass(q: number | null): string {
    if (q === null || q === undefined) return 'text-gray-400';
    if (q >= 0.85) return 'text-green-600';
    if (q >= 0.65) return 'text-blue-600';
    if (q >= 0.45) return 'text-yellow-600';
    return 'text-red-600';
  }
}
