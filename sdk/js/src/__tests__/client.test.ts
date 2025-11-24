/**
 * Client Tests
 */

import { DataHubClient } from '../client';
import { UnauthorizedError, NotFoundError, ValidationError } from '../errors';
import axios from 'axios';

jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('DataHubClient', () => {
  let client: DataHubClient;
  const mockAxiosInstance = {
    request: jest.fn(),
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
  };

  beforeEach(() => {
    jest.clearAllMocks();
    (axios.create as jest.Mock).mockReturnValue(mockAxiosInstance);
    
    client = new DataHubClient({
      baseUrl: 'https://api.example.com/api/v1',
      apiToken: 'test-token',
    });
  });

  describe('initialization', () => {
    it('should create axios instance with correct config', () => {
      expect(axios.create).toHaveBeenCalledWith(
        expect.objectContaining({
          baseURL: 'https://api.example.com/api/v1',
          timeout: 30000,
        })
      );
    });

    it('should throw error if baseUrl is missing', () => {
      expect(() => {
        new DataHubClient({ baseUrl: '' } as any);
      }).toThrow('baseUrl is required');
    });
  });

  describe('authentication', () => {
    it('should set API token in Authorization header', () => {
      const requestInterceptor = mockAxiosInstance.interceptors.request.use.mock.calls[0][0];
      const config = { headers: {} };
      requestInterceptor(config);
      
      expect(config.headers.Authorization).toBe('Bearer test-token');
    });

    it('should allow setting token after initialization', () => {
      client.setApiToken('new-token');
      const requestInterceptor = mockAxiosInstance.interceptors.request.use.mock.calls[0][0];
      const config = { headers: {} };
      requestInterceptor(config);
      
      expect(config.headers.Authorization).toBe('Bearer new-token');
    });
  });

  describe('error handling', () => {
    it('should parse and throw ValidationError for 400', async () => {
      const errorResponse = {
        response: {
          status: 400,
          data: {
            error: {
              code: 'VALIDATION_ERROR',
              message: 'Invalid input',
              http_status: 400,
              request_id: 'req-123',
            },
          },
        },
      };

      mockAxiosInstance.request.mockRejectedValueOnce(errorResponse);
      
      await expect(client.get('/test')).rejects.toThrow(ValidationError);
    });

    it('should parse and throw NotFoundError for 404', async () => {
      const errorResponse = {
        response: {
          status: 404,
          data: {
            error: {
              code: 'NOT_FOUND',
              message: 'Resource not found',
              http_status: 404,
            },
          },
        },
      };

      mockAxiosInstance.request.mockRejectedValueOnce(errorResponse);
      
      await expect(client.get('/test')).rejects.toThrow(NotFoundError);
    });
  });

  describe('retry logic', () => {
    it('should retry on 5xx errors', async () => {
      const errorResponse = {
        response: { status: 500 },
        request: {},
      };

      mockAxiosInstance.request
        .mockRejectedValueOnce(errorResponse)
        .mockRejectedValueOnce(errorResponse)
        .mockResolvedValueOnce({ data: { success: true } });

      jest.useFakeTimers();
      
      const promise = client.get('/test');
      
      // Fast-forward through retries
      jest.advanceTimersByTime(3000);
      
      await expect(promise).resolves.toEqual({ success: true });
      
      jest.useRealTimers();
    });

    it('should not retry on 4xx errors', async () => {
      const errorResponse = {
        response: { status: 400 },
        request: {},
      };

      mockAxiosInstance.request.mockRejectedValueOnce(errorResponse);
      
      await expect(client.get('/test')).rejects.toBeDefined();
      expect(mockAxiosInstance.request).toHaveBeenCalledTimes(1);
    });
  });
});

