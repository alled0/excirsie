import { APP_INITIALIZER, ApplicationConfig } from '@angular/core';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideAnimations } from '@angular/platform-browser/animations';

import { routes } from './app.routes';
import { RuntimeConfigService } from './services/runtime-config.service';
import { UserService } from './services/user.service';
import { userTokenInterceptor } from './interceptors/user-token.interceptor';

function initApp(configService: RuntimeConfigService, userService: UserService) {
  return async () => {
    await configService.load();
    await userService.init();
  };
}

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes, withComponentInputBinding()),
    provideHttpClient(withInterceptors([userTokenInterceptor])),
    provideAnimations(),
    {
      provide:    APP_INITIALIZER,
      useFactory: initApp,
      deps:       [RuntimeConfigService, UserService],
      multi:      true,
    },
  ],
};
