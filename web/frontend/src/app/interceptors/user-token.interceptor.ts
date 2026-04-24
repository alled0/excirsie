import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { UserService } from '../services/user.service';

/**
 * Adds the X-User-Id header to every /api/ request so controllers
 * can associate data with the current user without requiring it in every body.
 */
export const userTokenInterceptor: HttpInterceptorFn = (req, next) => {
  const userService = inject(UserService);
  const userId      = userService.userId;

  // Only attach to backend API calls, and skip the resolve call itself
  if (userId && req.url.includes('/api/') && !req.url.includes('/api/users/resolve')) {
    return next(req.clone({ setHeaders: { 'X-User-Id': userId } }));
  }

  return next(req);
};
