import { Request, Response, NextFunction } from 'express';

/**
 * Simple authentication middleware.
 *
 * Expects an `Authorization` header with the format:
 *   Bearer <token>
 *
 * For demo purposes the valid token is hard‑coded as `secret-token`.
 * In a real project this would verify a JWT, session cookie, etc.
 */
export function authMiddleware(req: Request, res: Response, next: NextFunction) {
  const authHeader = req.headers['authorization'];

  if (!authHeader) {
    return res.status(401).json({ error: 'Missing Authorization header' });
  }

  const parts = authHeader.split(' ');
  if (parts.length !== 2 || parts[0] !== 'Bearer') {
    return res.status(401).json({ error: 'Invalid Authorization format' });
  }

  const token = parts[1];
  if (token !== 'secret-token') {
    return res.status(401).json({ error: 'Invalid token' });
  }

  // Token is valid – proceed to the next handler
  next();
}
