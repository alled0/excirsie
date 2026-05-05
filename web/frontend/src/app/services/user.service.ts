import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, firstValueFrom } from 'rxjs';
import { RuntimeConfigService } from './runtime-config.service';

interface ResolvedUser {
  userId: string;
  token: string;
  isNew: boolean;
}

const TOKEN_KEY  = 'workout_token';
const USER_ID_KEY = 'workout_user_id';

@Injectable({ providedIn: 'root' })
export class UserService {
  private readonly userId$ = new BehaviorSubject<string | null>(
    localStorage.getItem(USER_ID_KEY)
  );

  constructor(
    private http: HttpClient,
    private runtimeConfig: RuntimeConfigService,
  ) {}

  get userId(): string | null {
    return this.userId$.value;
  }

  /**
   * Called once on app startup via APP_INITIALIZER.
   * Generates a UUID token if this is the first visit, then resolves it
   * with the backend to get the internal userId.
   */
  async init(): Promise<void> {
    let token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      token = crypto.randomUUID();
      localStorage.setItem(TOKEN_KEY, token);
    }

    try {
      const res = await firstValueFrom(
        this.http.post<ResolvedUser>(`${this.runtimeConfig.apiBase}/users/resolve`, { token })
      );
      localStorage.setItem(TOKEN_KEY,   res.token);
      localStorage.setItem(USER_ID_KEY, res.userId);
      this.userId$.next(res.userId);
    } catch {
      // Offline or backend not running — continue without a userId.
      // The interceptor simply omits the header when userId is null.
    }
  }
}
