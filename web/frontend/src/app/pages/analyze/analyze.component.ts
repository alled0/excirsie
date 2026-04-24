import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { NgFor, NgIf } from '@angular/common';

import { ApiService } from '../../services/api.service';
import { Exercise } from '../../models/exercise.model';

@Component({
  selector: 'app-analyze',
  standalone: true,
  imports: [FormsModule, NgFor, NgIf],
  templateUrl: './analyze.component.html',
})
export class AnalyzeComponent implements OnInit {
  exercises: Exercise[] = [];
  selectedKey = '';
  selectedFile: File | null = null;
  isDragging = false;
  isAnalysing = false;
  errorMessage = '';

  constructor(private api: ApiService, private router: Router) {}

  ngOnInit(): void {
    this.api.getExercises().subscribe({
      next: (list) => {
        this.exercises = list;
        if (list.length) this.selectedKey = list[0].key;
      },
      error: () => {
        this.errorMessage = 'Could not load exercises. Is the backend running?';
      },
    });
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.isDragging = true;
  }

  onDragLeave(): void {
    this.isDragging = false;
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.isDragging = false;
    const file = event.dataTransfer?.files[0];
    if (file) this.setFile(file);
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file) this.setFile(file);
  }

  private setFile(file: File): void {
    if (!file.type.startsWith('video/')) {
      this.errorMessage = 'Please upload a video file (mp4, mov, avi…)';
      return;
    }
    this.selectedFile = file;
    this.errorMessage = '';
  }

  get selectedExerciseName(): string {
    return this.exercises.find((e) => e.key === this.selectedKey)?.name ?? '';
  }

  get fileSizeMb(): string {
    if (!this.selectedFile) return '';
    return (this.selectedFile.size / 1_048_576).toFixed(1);
  }

  submit(): void {
    if (!this.selectedFile || !this.selectedKey) return;

    this.isAnalysing = true;
    this.errorMessage = '';

    this.api.analyzeVideo(this.selectedFile, this.selectedKey).subscribe({
      next: (result) => {
        this.router.navigateByUrl('/results', { state: { result } });
      },
      error: (err) => {
        this.isAnalysing = false;
        this.errorMessage =
          err?.error?.error ?? 'Something went wrong. Please try again.';
      },
    });
  }
}
