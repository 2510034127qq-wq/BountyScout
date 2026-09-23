import express, { Application } from 'express';
import { json } from 'body-parser';
import { proposalsRouter } from './routes/proposals';

export function createApp(): Application {
  const app = express();

  // Global middlewares
  app.use(json());

  // Mount API routers
  app.use('/api/proposals', proposalsRouter);

  // Default 404 handler for unknown routes
  app.use((_req, res) => {
    res.status(404).json({ error: 'Not Found' });
  });

  return app;
}
