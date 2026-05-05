import { Injectable } from '@angular/core';

export interface RuntimeConfig {
  // Backend REST API base. Usually /api or https://backend.example.com/api.
  apiBase: string;

  // REST analysis gateway. Defaults to backend /api so uploads flow through Spring.
  modelBase: string;

  // Live model WebSocket base. Example: ws://localhost:8081/ws or /ws behind nginx.
  wsBase: string;
}

const DEFAULT_CONFIG: RuntimeConfig = {
  apiBase: '/api',
  modelBase: '/api',
  wsBase: 'ws://localhost:8081/ws',
};

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, '');
}

@Injectable({ providedIn: 'root' })
export class RuntimeConfigService {
  private config: RuntimeConfig = DEFAULT_CONFIG;

  async load(): Promise<void> {
    try {
      const res = await fetch('/assets/runtime-config.json', { cache: 'no-store' });
      if (!res.ok) return;
      const loaded = await res.json() as Partial<RuntimeConfig>;
      this.config = {
        apiBase: trimTrailingSlash(loaded.apiBase ?? DEFAULT_CONFIG.apiBase),
        modelBase: trimTrailingSlash(loaded.modelBase ?? DEFAULT_CONFIG.modelBase),
        wsBase: trimTrailingSlash(loaded.wsBase ?? DEFAULT_CONFIG.wsBase),
      };
    } catch {
      this.config = DEFAULT_CONFIG;
    }
  }

  get apiBase(): string {
    return this.config.apiBase;
  }

  get modelBase(): string {
    return this.config.modelBase;
  }

  get wsBase(): string {
    if (!this.config.wsBase.startsWith('/')) {
      return this.config.wsBase;
    }
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}${this.config.wsBase}`;
  }
}
