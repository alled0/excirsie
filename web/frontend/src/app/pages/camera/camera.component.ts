import {
  Component, OnInit, OnDestroy,
  ViewChild, ElementRef,
} from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { NgFor, NgIf, NgClass } from '@angular/common';
import { Subscription } from 'rxjs';

import { ApiService } from '../../services/api.service';
import { WorkoutSocketService, LiveFeedback } from '../../services/workout-socket.service';
import { Exercise } from '../../models/exercise.model';

@Component({
  selector: 'app-camera',
  standalone: true,
  imports: [RouterLink, FormsModule, NgFor, NgIf, NgClass],
  templateUrl: './camera.component.html',
})
export class CameraComponent implements OnInit, OnDestroy {
  @ViewChild('videoEl', { static: false }) videoEl!: ElementRef<HTMLVideoElement>;
  @ViewChild('canvasEl', { static: false }) canvasEl!: ElementRef<HTMLCanvasElement>;

  exercises: Exercise[] = [];
  selectedKey = '';

  cameraActive = false;
  sessionActive = false;
  connected = false;
  permissionDenied = false;
  loadError = false;

  feedback: LiveFeedback | null = null;

  private stream: MediaStream | null = null;
  private captureInterval: ReturnType<typeof setInterval> | null = null;
  private subs = new Subscription();

  // Target send rate — 10 fps is enough for meaningful feedback without flooding the socket
  private readonly CAPTURE_MS = 100;

  constructor(
    private api: ApiService,
    private socket: WorkoutSocketService,
    private route: ActivatedRoute,
    private router: Router,
  ) {}

  ngOnInit(): void {
    this.api.getExercises().subscribe({
      next: (list) => {
        this.exercises = list;
        const key = this.route.snapshot.queryParamMap.get('exercise');
        this.selectedKey = key && list.some((e) => e.key === key) ? key : list[0]?.key ?? '';
      },
      error: () => (this.loadError = true),
    });

    this.subs.add(
      this.socket.connected$.subscribe((c) => (this.connected = c))
    );

    this.subs.add(
      this.socket.feedback$.subscribe((fb) => (this.feedback = fb))
    );
  }

  async startCamera(): Promise<void> {
    this.permissionDenied = false;
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false,
      });
      this.cameraActive = true;
      // Wait one tick for @ViewChild to bind after *ngIf becomes true
      setTimeout(() => {
        this.videoEl.nativeElement.srcObject = this.stream;
      }, 0);
    } catch {
      this.permissionDenied = true;
    }
  }

  startSession(): void {
    if (!this.selectedKey || !this.cameraActive) return;
    this.feedback = null;
    this.socket.connect(this.selectedKey);
    this.sessionActive = true;
    this.captureInterval = setInterval(() => this.captureAndSend(), this.CAPTURE_MS);
  }

  stopSession(): void {
    if (this.captureInterval) {
      clearInterval(this.captureInterval);
      this.captureInterval = null;
    }
    this.socket.disconnect();
    this.sessionActive = false;

    // Save the session to history if any reps were counted
    if (this.feedback && this.feedback.reps_total > 0) {
      this.api.saveLiveSession({
        exercise_key:  this.selectedKey,
        reps_total:    this.feedback.reps_total,
        reps_left:     this.feedback.reps_left ?? null,
        reps_right:    this.feedback.reps_right ?? null,
      }).subscribe();
    }
  }

  stopCamera(): void {
    this.stopSession();
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    this.cameraActive = false;
    this.feedback = null;
  }

  private captureAndSend(): void {
    const video  = this.videoEl?.nativeElement;
    const canvas = this.canvasEl?.nativeElement;
    if (!video || !canvas || video.readyState < 2) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width  = video.videoWidth  || 640;
    canvas.height = video.videoHeight || 480;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(
      (blob) => { if (blob) this.socket.sendFrame(blob); },
      'image/jpeg',
      0.7,  // 70% quality — good balance between detail and bandwidth
    );
  }

  get severityClass(): string {
    switch (this.feedback?.severity) {
      case 'error':   return 'bg-red-500 text-white';
      case 'warning': return 'bg-yellow-400 text-gray-900';
      default:        return 'bg-green-500 text-white';
    }
  }

  get qualityDot(): string {
    switch (this.feedback?.quality) {
      case 'GOOD': return 'bg-green-400';
      case 'WEAK': return 'bg-yellow-400';
      default:     return 'bg-red-400';
    }
  }

  ngOnDestroy(): void {
    this.stopCamera();
    this.subs.unsubscribe();
  }
}
