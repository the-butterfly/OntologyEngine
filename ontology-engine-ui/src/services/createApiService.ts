/**
 * Generic API service factory for CRUD operations.
 *
 * Provides a type-safe wrapper around apiClient with:
 * - Automatic response unwrapping ({ success, data, meta, error })
 * - Consistent error handling
 * - URL path interpolation
 */

import { apiClient } from '../api/client';
import axios from 'axios';

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
    async get<R = T>(path: string, params?: Record<string, any>): Promise<R> {
      try {
        const response = await apiClient.get<ApiResponse<R>>(`${basePath}${path}`, { params });
        return unwrapResponse(response.data);
      } catch (error) {
        throw extractApiError(error);
      }
    },

    async post<R = T>(path: string, data?: Record<string, any>): Promise<R> {
      try {
        const response = await apiClient.post<ApiResponse<R>>(`${basePath}${path}`, data);
        return unwrapResponse(response.data);
      } catch (error) {
        throw extractApiError(error);
      }
    },

    async put<R = T>(path: string, data?: Record<string, any>): Promise<R> {
      try {
        const response = await apiClient.put<ApiResponse<R>>(`${basePath}${path}`, data);
        return unwrapResponse(response.data);
      } catch (error) {
        throw extractApiError(error);
      }
    },

    async patch<R = T>(path: string, data?: Record<string, any>): Promise<R> {
      try {
        const response = await apiClient.patch<ApiResponse<R>>(`${basePath}${path}`, data);
        return unwrapResponse(response.data);
      } catch (error) {
        throw extractApiError(error);
      }
    },

    async delete<R = T>(path: string): Promise<R> {
      try {
        const response = await apiClient.delete<ApiResponse<R>>(`${basePath}${path}`);
        return unwrapResponse(response.data);
      } catch (error) {
        throw extractApiError(error);
      }
    },
  };
}

function extractApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error) && error.response?.data?.error) {
    const { code, message } = error.response.data.error;
    return new ApiError(message, code);
  }
  if (error instanceof Error) {
    return new ApiError(error.message, 'NETWORK_ERROR');
  }
  return new ApiError('Unknown error', 'UNKNOWN_ERROR');
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
