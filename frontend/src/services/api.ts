/** API service functions */

import { API_URLS } from '../config/api';

export interface UploadDocumentRequest {
  filename: string;
  mime_type?: string;
  file_b64?: string;
  text?: string;
}

export interface UploadDocumentResponse {
  document_id: string;
  filename: string;
  total_chunks: number;
  chunks_created: number;
}

export interface QueryRequest {
  question: string;
  max_chunks?: number;
  max_tokens?: number;
}

export interface Source {
  document_id: string;
  chunk_index: number;
  content: string;
}

export interface QueryResponse {
  answer: string;
  sources: Source[];
  total_chunks: number;
}

export class ApiService {
  private static async request<T>(
    url: string,
    options: RequestInit = {}
  ): Promise<T> {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`API Error: ${response.status} ${error}`);
    }

    return response.json();
  }

  static async uploadDocument(data: UploadDocumentRequest): Promise<UploadDocumentResponse> {
    return this.request<UploadDocumentResponse>(API_URLS.INGEST, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  static async query(data: QueryRequest): Promise<QueryResponse> {
    return this.request<QueryResponse>(API_URLS.QUERY, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  static async healthCheck(): Promise<{ status: string }> {
    return this.request<{ status: string }>(API_URLS.HEALTH);
  }

  static async deleteDocument(documentId: string): Promise<{ message: string }> {
    return this.request<{ message: string }>(`${API_CONFIG.BASE_URL}/api/v1/ingest/${documentId}`, {
      method: 'DELETE',
    });
  }
}
