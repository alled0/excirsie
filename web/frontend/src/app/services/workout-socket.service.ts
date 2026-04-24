import { Injectable, NgZone } from '@angular/core';
import { Subject } from 'rxjs';

export interface PoseLandmark {
  x: number;
  y: number;
  z?: number;
  visibility?: number;
  presence?: number;
}

export interface LiveFeedback {
  detected: boolean;
  reps_total: number;
  reps_left?: number | null;
  reps_right?: number | null;
  quality: 'GOOD' | 'WEAK' | 'LOST';
  feedback: string;
  severity: 'ok' | 'warning' | 'error';
  angles?: (number | null)[];
  landmarks?: PoseLandmark[];
}

@Injectable({ providedIn: 'root' })
export class WorkoutSocketService {
  private socket: WebSocket | null = null;

  readonly feedback$ = new Subject<LiveFeedback>();
  readonly connected$ = new Subject<boolean>();

  constructor(private zone: NgZone) {}

  connect(exerciseKey: string): void {
    this.disconnect();

    // In dev the Angular proxy only covers /api, so WebSocket goes directly to port 8081.
    // In production, update this to wss://your-domain/ws/live/...
    const wsUrl = `ws://localhost:8081/ws/live/${exerciseKey}`;
    this.socket = new WebSocket(wsUrl);
    this.socket.binaryType = 'arraybuffer';

    this.socket.onopen = () => {
      this.zone.run(() => this.connected$.next(true));
    };

    this.socket.onmessage = (event: MessageEvent) => {
      try {
        const data: LiveFeedback = JSON.parse(event.data as string);
        this.zone.run(() => this.feedback$.next(data));
      } catch {
        // malformed message — ignore
      }
    };

    this.socket.onclose = () => {
      this.zone.run(() => this.connected$.next(false));
    };
  }

  sendFrame(jpeg: Blob): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(jpeg);
    }
  }

  disconnect(): void {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }
}
