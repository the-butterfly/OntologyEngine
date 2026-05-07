/**
 * Generic API service factory for CRUD operations.
 *
 * Provides a type-safe wrapper around apiClient with:
 * - Automatic response unwrapping ({ success, data, meta, error })
 * - Consistent error handling
 * - URL path interpolation
 */

import { apiClient } from '../api/client';

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  meta?: Record<string, any>;
  error?: { code: string; message: string } | null;
}

export interface ApiServiceConfig {
  basePath: string;
}

export function createApiService<T>(config: ApiServiceConfig) {
  const { basePath } = config;

  return {
    /**
     * GET request
     */
    async get<R = T>(path: string, params?: Record<string, any>): Promise<R> {
      const response = await apiClient.get<ApiResponse<R>>(`${basePath}${path}`, { params });
      return unwrapResponse(response.data);
    },

    /**
     * POST request
     */
    async post<R = T>(path: string, data?: Record<string, any>): Promise<R> {
      const response = await apiClient.post<ApiResponse<R>>(`${basePath}${path}`, data);
      return unwrapResponse(response.data);
    },

    /**
     * PUT request
     */
    async put<R = T>(path: string, data?: Record<string, any>): Promise<R> {
      const response = await apiClient.put<ApiResponse<R>>(`${basePath}${path}`, data);
      return unwrapResponse(response.data);
    },

    /**
     * PATCH request
     */
    async patch<R = T>(path: string, data?: Record<string, any>): Promise<R> {
      const response = await apiClient.patch<ApiResponse<R>>(`${basePath}${path}`, data);
      return unwrapResponse(response.data);
    },

    /**
     * DELETE request
     */
    async delete<R = T>(path: string): Promise<R> {
      const response = await apiClient.delete<ApiResponse<R>>(`${basePath}${path}`);
      return unwrapResponse(response.data);
    },
  };
}

function unwrapResponse<T>(response: ApiResponse<T>): T {
  if (!response.success) {
    const errorMessage = response.error?.message || 'Unknown API error';
    const errorCode = response.error?.code || 'UNKNOWN_ERROR';
    throw new ApiError(errorMessage, errorCode);
  }
  return response.data;
}

export class ApiError extends Error {
  code: string;

  constructor(message: string, code: string) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
  }
}
