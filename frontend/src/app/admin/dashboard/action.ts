'use server';

import { authFetch } from "@/lib/auth";
import { apiEndpoint } from "@/common/constants/api";

export async function getAdminStats() {
  const res = await authFetch(apiEndpoint("admin/dashboard/"));

  if (!res.ok) {
    if (res.status === 401 || res.status === 403) {
      return { error: 'unauthorized' };
    }
    return { error: 'failed' };
  }

  const data = await res.json();
  
  // Transform data to flat structure if needed
  if (data.stats) {
    return {
      ...data,
      ...data.stats
    };
  }
  
  return data;
}