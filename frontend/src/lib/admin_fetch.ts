import { clientAuthFetch, refreshAuthToken } from '@/lib/auth_client';

export async function adminGet<T>(url: string, options?: RequestInit): Promise<Response> {
  let response = await clientAuthFetch(url, {
    method: 'GET',
    ...options,
  });

  // Handle token refresh if 401
  if (response.status === 401) {
    const refreshed = await refreshAuthToken();
    if (refreshed) {
      response = await clientAuthFetch(url, {
        method: 'GET',
        ...options,
      });
    }
  }

  return response;
}

export async function adminPost<T>(url: string, body: any, options?: RequestInit): Promise<Response> {
  let response = await clientAuthFetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    body: JSON.stringify(body),
    ...options,
  });

  if (response.status === 401) {
    const refreshed = await refreshAuthToken();
    if (refreshed) {
      response = await clientAuthFetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
        body: JSON.stringify(body),
        ...options,
      });
    }
  }

  return response;
}