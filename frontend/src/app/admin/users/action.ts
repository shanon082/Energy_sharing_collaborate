'use server';

import { authFetch } from "@/lib/auth";

export async function getUsers() {
  const API_BASE = 'http://localhost:8000/api/v1';
  const res = await authFetch(`${API_BASE}/admin/users/`);

  if (!res.ok) {
    if (res.status === 401 || res.status === 403) {
      return { error: 'unauthorized' };
    }
    return { error: 'failed' };
  }

  const data = await res.json();
  
  if (data.stats) {
    return {
      ...data,
      ...data.stats
    };
  }
  
  return data;
}