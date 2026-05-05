import { Injectable, NgZone } from '@angular/core';
import { Subject } from 'rxjs';
import { RuntimeConfigService } from './runtime-config.service';

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
  server_processing_ms?: number;
}

@Injectable({ providedIn: 'root' })
export class WorkoutSocketService {
  private socket: WebSocket | null = null;
  private awaitingResponse = false;
  private lastSendAt = 0;

  private readonly MAX_IN_FLIGHT_MS = 1500;

  readonly feedback$ = new Subject<LiveFeedback>();
  readonly connected$ = new Subject<boolean>();

  constructor(
    private zone: NgZone,
    private runtimeConfig: RuntimeConfigService,
  ) {}

  connect(exerciseKey: string): void {
    this.disconnect();
    this.awaitingResponse = false;
    this.lastSendAt = 0;

    const wsUrl = `${this.runtimeConfig.wsBase}/live/${exerciseKey}`;
    this.socket = new WebSocket(wsUrl);
    this.socket.binaryType = 'arraybuffer';

    this.socket.onopen = () => {
      this.zone.run(() => this.connected$.next(true));
    };

    this.socket.onmessage = (event: MessageEvent) => {
      this.awaitingResponse = false;
      try {
        const data: LiveFeedback = JSON.parse(event.data as string);
        this.zone.run(() => this.feedback$.next(data));
      } catch {
        // Ignore malformed websocket messages without breaking the live loop.
      }
    };

    this.socket.onclose = () => {
      this.awaitingResponse = false;
      this.zone.run(() => this.connected$.next(false));
    };
  }

  sendFrame(jpeg: Blob): boolean {
    if (this.socket?.readyState !== WebSocket.OPEN) {
      return false;
    }
    const now = performance.now();
    if (this.awaitingResponse && now - this.lastSendAt < this.MAX_IN_FLIGHT_MS) {
      return false;
    }
    if (this.socket.bufferedAmount > 0) {
      return false;
    }

    this.awaitingResponse = true;
    this.lastSendAt = now;
    this.socket.send(jpeg);
    return true;
  }

  disconnect(): void {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
    this.awaitingResponse = false;
    this.lastSendAt = 0;
  }
}
