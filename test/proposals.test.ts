import request from 'supertest';
import { createApp } from '../src/app';

describe('POST /api/proposals', () => {
  const app = createApp();

  const validToken = 'secret-token';
  const authHeader = `Bearer ${validToken}`;

  it('should reject requests without Authorization header', async () => {
    const response = await request(app)
      .post('/api/proposals')
      .send({ title: 'Test', description: 'Desc' });

    expect(response.status).toBe(401);
    expect(response.body).toHaveProperty('error');
  });

  it('should reject requests with invalid token', async () => {
    const response = await request(app)
      .post('/api/proposals')
      .set('Authorization', 'Bearer wrong-token')
      .send({ title: 'Test', description: 'Desc' });

    expect(response.status).toBe(401);
    expect(response.body).toHaveProperty('error');
  });

  it('should validate required fields', async () => {
    const response = await request(app)
      .post('/api/proposals')
      .set('Authorization', authHeader)
      .send({ title: '' });

    expect(response.status).toBe(400);
    expect(response.body).toHaveProperty('error');
  });

  it('should create a proposal when authenticated and payload is valid', async () => {
    const payload = {
      title: 'New Feature',
      description: 'Add a new endpoint',
      bounty: 100,
    };

    const response = await request(app)
      .post('/api/proposals')
      .set('Authorization', authHeader)
      .send(payload);

    expect(response.status).toBe(201);
    expect(response.body).toMatchObject({
      title: payload.title,
      description: payload.description,
      bounty: payload.bounty,
    });
    expect(response.body).toHaveProperty('id');
    expect(response.body).toHaveProperty('createdAt');
  });
});
