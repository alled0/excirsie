import {
  Component, OnInit, OnDestroy,
  ViewChild, ElementRef,
} from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { NgFor, NgIf, NgClass } from '@angular/common';
import { Subscription } from 'rxjs';

import { ApiService } from '../../services/api.service';
import {
  WorkoutSocketService,
  LiveFeedback,
  PoseLandmark,
} from '../../services/workout-socket.service';
import { Exercise } from '../../models/exercise.model';

@Component({
  selector: 'app-camera',
  standalone: true,
  imports: [RouterLink, FormsModule, NgFor, NgIf, NgClass],
  templateUrl: './camera.component.html',
})
export class CameraComponent implements OnInit, OnDestroy {
  @ViewChild('videoEl', { static: false }) videoEl!: ElementRef<HTMLVideoElement>;
  @ViewChild('captureCanvasEl', { static: false }) captureCanvasEl!: ElementRef<HTMLCanvasElement>;
  @ViewChild('overlayCanvasEl', { static: false }) overlayCanvasEl!: ElementRef<HTMLCanvasElement>;

  exercises: Exercise[] = [];
  selectedKey = '';
  showSkeleton = true;

  cameraActive = false;
  sessionActive = false;
  connected = false;
  permissionDenied = false;
  loadError = false;

  feedback: LiveFeedback | null = null;

  private stream: MediaStream | null = null;
  private captureInterval: ReturnType<typeof setInterval> | null = null;
  private overlayStaleTimer: ReturnType<typeof setTimeout> | null = null;
  private captureBusy = false;
  private subs = new Subscription();

  // Target send rate. Backpressure in the socket service drops stale frames.
  private readonly CAPTURE_MS = 80;
  private readonly CAPTURE_MAX_WIDTH = 360;
  private readonly JPEG_QUALITY = 0.55;
  private readonly OVERLAY_STALE_MS = 350;
  private readonly MIN_DRAW_VISIBILITY = 0.2;
  private readonly SKELETON_CONNECTIONS: ReadonlyArray<readonly [number, number]> = [
    [0, 2], [0, 5], [2, 7], [5, 8],
    [9, 10],
    [11, 12],
    [11, 13], [13, 15], [15, 17], [15, 19], [15, 21],
    [12, 14], [14, 16], [16, 18], [16, 20], [16, 22],
    [11, 23], [12, 24], [23, 24],
    [23, 25], [25, 27], [27, 29], [29, 31],
    [24, 26], [26, 28], [28, 30], [30, 32],
  ];

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
      this.socket.feedback$.subscribe((fb) => {
        this.feedback = fb;
        this.drawOverlay();
        this.scheduleOverlayExpiry();
      })
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
        const video = this.videoEl.nativeElement;
        video.srcObject = this.stream;
        video.onloadedmetadata = () => {
          void video.play().catch(() => undefined);
          this.syncOverlayCanvas();
          this.clearOverlay();
        };
      }, 0);
    } catch {
      this.permissionDenied = true;
    }
  }

  startSession(): void {
    if (!this.selectedKey || !this.cameraActive) return;
    this.feedback = null;
    this.clearOverlay();
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
    this.clearOverlay();

    // Save the session to history if any reps were counted
    if (this.feedback && this.feedback.reps_total > 0) {
      const exerciseName = this.exercises.find((e) => e.key === this.selectedKey)?.name ?? '';
      this.api.saveSession({
        exerciseKey:  this.selectedKey,
        exerciseName: exerciseName,
        source:       'live',
        repsTotal:    this.feedback.reps_total,
        repsLeft:     this.feedback.reps_left  ?? null,
        repsRight:    this.feedback.reps_right ?? null,
      }).subscribe();
    }
  }

  stopCamera(): void {
    this.stopSession();
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    this.cameraActive = false;
    this.feedback = null;
    this.clearOverlay();
  }

  private captureAndSend(): void {
    const video = this.videoEl?.nativeElement;
    const canvas = this.captureCanvasEl?.nativeElement;
    if (!video || !canvas || video.readyState < 2 || this.captureBusy) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const videoWidth = video.videoWidth || 640;
    const videoHeight = video.videoHeight || 480;
    const scale = Math.min(1, this.CAPTURE_MAX_WIDTH / videoWidth);
    const captureWidth = Math.max(1, Math.round(videoWidth * scale));
    const captureHeight = Math.max(1, Math.round(videoHeight * scale));

    if (canvas.width !== captureWidth) canvas.width = captureWidth;
    if (canvas.height !== captureHeight) canvas.height = captureHeight;
    this.syncOverlayCanvas();
    ctx.drawImage(video, 0, 0, captureWidth, captureHeight);

    this.captureBusy = true;
    canvas.toBlob(
      (blob) => {
        this.captureBusy = false;
        if (blob) this.socket.sendFrame(blob);
      },
      'image/jpeg',
      this.JPEG_QUALITY,
    );
  }

  onSkeletonToggle(): void {
    this.drawOverlay();
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

  private syncOverlayCanvas(): void {
    const video = this.videoEl?.nativeElement;
    const overlay = this.overlayCanvasEl?.nativeElement;
    if (!video || !overlay) return;

    const width = video.videoWidth || 640;
    const height = video.videoHeight || 480;
    if (overlay.width !== width) overlay.width = width;
    if (overlay.height !== height) overlay.height = height;
  }

  private clearOverlay(): void {
    if (this.overlayStaleTimer) {
      clearTimeout(this.overlayStaleTimer);
      this.overlayStaleTimer = null;
    }

    const overlay = this.overlayCanvasEl?.nativeElement;
    if (!overlay) return;
    this.syncOverlayCanvas();
    const ctx = overlay.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, overlay.width, overlay.height);
  }

  private scheduleOverlayExpiry(): void {
    if (this.overlayStaleTimer) {
      clearTimeout(this.overlayStaleTimer);
    }

    this.overlayStaleTimer = setTimeout(() => {
      this.overlayStaleTimer = null;
      this.clearOverlay();
    }, this.OVERLAY_STALE_MS);
  }

  private drawOverlay(): void {
    const overlay = this.overlayCanvasEl?.nativeElement;
    const video = this.videoEl?.nativeElement;
    if (!overlay || !video) return;

    this.syncOverlayCanvas();
    const ctx = overlay.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, overlay.width, overlay.height);

    if (
      !this.showSkeleton ||
      !this.sessionActive ||
      !this.feedback?.detected ||
      !this.feedback.landmarks?.length
    ) {
      return;
    }

    const landmarks = this.feedback.landmarks;
    const lineWidth = Math.max(2, overlay.width / 320);

    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.82)';
    ctx.lineWidth = lineWidth;

    for (const [fromIndex, toIndex] of this.SKELETON_CONNECTIONS) {
      const start = landmarks[fromIndex];
      const end = landmarks[toIndex];
      if (!this.isDrawable(start) || !this.isDrawable(end)) {
        continue;
      }
      ctx.globalAlpha = Math.min(this.landmarkAlpha(start), this.landmarkAlpha(end));
      ctx.beginPath();
      ctx.moveTo(start.x * overlay.width, start.y * overlay.height);
      ctx.lineTo(end.x * overlay.width, end.y * overlay.height);
      ctx.stroke();
    }

    for (const landmark of landmarks) {
      if (!this.isDrawable(landmark)) {
        continue;
      }
      const x = landmark.x * overlay.width;
      const y = landmark.y * overlay.height;
      ctx.globalAlpha = this.landmarkAlpha(landmark);
      ctx.fillStyle = 'rgba(250, 204, 21, 0.95)';
      ctx.beginPath();
      ctx.arc(x, y, Math.max(3, lineWidth * 0.95), 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.globalAlpha = 1;
  }

  private isDrawable(landmark?: PoseLandmark): landmark is PoseLandmark {
    return !!landmark && this.landmarkScore(landmark) >= this.MIN_DRAW_VISIBILITY;
  }

  private landmarkScore(landmark: PoseLandmark): number {
    return Math.min(landmark.visibility ?? 1, landmark.presence ?? 1);
  }

  private landmarkAlpha(landmark: PoseLandmark): number {
    return Math.max(0.35, Math.min(1, this.landmarkScore(landmark)));
  }

  ngOnDestroy(): void {
    this.stopCamera();
    if (this.overlayStaleTimer) {
      clearTimeout(this.overlayStaleTimer);
      this.overlayStaleTimer = null;
    }
    this.subs.unsubscribe();
  }
}
