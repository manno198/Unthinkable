/** API configuration and endpoints */

export const API_CONFIG = {
  BASE_URL: import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000',
  ENDPOINTS: {
    INGEST: '/api/v1/ingest/upload',
    QUERY: '/api/v1/query/ask',
    HEALTH: '/health'
  }
} as const;

export const API_URLS = {
  INGEST: `${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.INGEST}`,
  QUERY: `${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.QUERY}`,
  HEALTH: `${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.HEALTH}`
} as const;
