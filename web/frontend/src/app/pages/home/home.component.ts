import { Component, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { NgFor, NgIf } from '@angular/common';

import { ApiService } from '../../services/api.service';
import { Exercise } from '../../models/exercise.model';

const EXERCISE_ICONS: Record<string, string> = {
  '1': '💪',
  '2': '🏋️',
  '3': '↔️',
  '4': '🔁',
  '5': '🦵',
};

const EXERCISE_DESC: Record<string, string> = {
  '1': 'Counts reps and flags swinging or incomplete range of motion.',
  '2': 'Checks lockout, lean-back, and wrist alignment.',
  '3': 'Flags raising too high or below shoulder height.',
  '4': 'Monitors elbow flare and full extension.',
  '5': 'Checks squat depth and forward lean.',
};

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [RouterLink, NgFor, NgIf],
  templateUrl: './home.component.html',
})
export class HomeComponent implements OnInit {
  exercises: Exercise[] = [];
  icons = EXERCISE_ICONS;
  descriptions = EXERCISE_DESC;
  loadError = false;

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.api.getExercises().subscribe({
      next: (list) => (this.exercises = list),
      error: () => (this.loadError = true),
    });
  }
}
