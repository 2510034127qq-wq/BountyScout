import { Router, Request, Response } from 'express';
import { authMiddleware } from '../middleware/auth';

export const proposalsRouter = Router();

/**
 * POST /api/proposals
 *
 * Protected by `authMiddleware`. Accepts a JSON payload describing a proposal.
 * Returns the created proposal with a generated ID.
 */
proposalsRouter.post('/', authMiddleware, (req: Request, res: Response) => {
  const { title, description, bounty } = req.body;

  if (!title || !description) {
    return res.status(400).json({ error: 'Missing required fields: title, description' });
  }

  // In a real implementation this would persist to a DB.
  const createdProposal = {
    id: Date.now().toString(),
    title,
    description,
    bounty: bounty ?? null,
    createdAt: new Date().toISOString(),
  };

  return res.status(201).json(createdProposal);
});
