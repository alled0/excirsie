import { APP_INITIALIZER, ApplicationConfig } from '@angular/core';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideAnimations } from '@angular/platform-browser/animations';

import { routes } from './app.routes';
import { UserService } from './services/user.service';
import { userTokenInterceptor } from './interceptors/user-token.interceptor';

function initUser(userService: UserService) {
  return () => userService.init();
}

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes, withComponentInputBinding()),
    provideHttpClient(withInterceptors([userTokenInterceptor])),
    provideAnimations(),
    {
      provide:    APP_INITIALIZER,
      useFactory: initUser,
      deps:       [UserService],
      multi:      true,
    },
  ],
};
