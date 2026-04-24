import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { Exercise } from '../models/exercise.model';
import { AnalysisResult } from '../models/analysis.model';

export interface FeedbackPayload {
  sessionId?: string;
  exerciseKey: string;
  rating: number;
  repCountAccurate: boolean;
  userRepCorrection?: number | null;
  comment: string;
}

export interface SaveSessionPayload {
  exerciseKey: string;
  exerciseName: string;
  source: 'upload' | 'live';
  repsTotal: number;
  repsLeft?: number | null;
  repsRight?: number | null;
  signalQuality?: number | null;
  dropoutRate?: number | null;
  meanReliability?: number | null;
  unknownRate?: number | null;
  framesTotal?: number | null;
  framesDetected?: number | null;
  fpsMean?: number | null;
  repsAborted?: number;
  repsRejected?: number;
  cameraIssues?: string[];
  durationS?: number | null;
}

export interface HistoryRecord {
  id: string;
  exerciseKey: string;
  exerciseName: string;
  source: 'upload' | 'live';
  repsTotal: number;
  repsLeft: number | null;
  repsRight: number | null;
  signalQuality: number | null;
  dropoutRate: number | null;
  meanReliability: number | null;
  framesTotal: number | null;
  framesDetected: number | null;
  createdAt: string;
}

export interface EventPayload {
  eventType: string;
  sessionId?: string | null;
  properties?: Record<string, unknown>;
  occurredAt?: string;
}

export interface ErrorPayload {
  sessionId?: string | null;
  errorType: string;
  message?: string;
  stackHash?: string;
  httpStatus?: number;
  occurredAt?: string;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  // Analysis calls go directly to the Python service (pure computation, no auth needed)
  private readonly modelBase = 'http://localhost:8081';

  // Session history, feedback, events, errors go through Spring Boot (persisted, user-linked)
  private readonly apiBase = '/api';

  constructor(private http: HttpClient) {}

  getExercises(): Observable<Exercise[]> {
    return this.http.get<Exercise[]>(`${this.modelBase}/exercises`);
  }

  analyzeVideo(file: File, exerciseKey: string): Observable<AnalysisResult> {
    const form = new FormData();
    form.append('video', file, file.name);
    form.append('exercise_key', exerciseKey);
    return this.http.post<AnalysisResult>(`${this.modelBase}/process`, form);
  }

  saveSession(payload: SaveSessionPayload): Observable<{ sessionId: string }> {
    return this.http.post<{ sessionId: string }>(`${this.apiBase}/sessions`, payload);
  }

  getHistory(): Observable<HistoryRecord[]> {
    return this.http.get<HistoryRecord[]>(`${this.apiBase}/sessions`);
  }

  submitFeedback(payload: FeedbackPayload): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(`${this.apiBase}/feedback`, payload);
  }

  trackEvents(events: EventPayload[]): void {
    const stamped = events.map((e) => ({
      ...e,
      occurredAt: e.occurredAt ?? new Date().toISOString(),
      properties: JSON.stringify(e.properties ?? {}),
    }));
    this.http.post(`${this.apiBase}/events`, { events: stamped }).subscribe();
  }

  reportError(payload: ErrorPayload): void {
    this.http.post(`${this.apiBase}/errors`, {
      ...payload,
      occurredAt: payload.occurredAt ?? new Date().toISOString(),
    }).subscribe();
  }
}
