'use server';

import { authFetch } from "@/lib/auth";
import { apiEndpoint } from "@/common/constants/api";

export async function getUsers() {
  const res = await authFetch(apiEndpoint("admin/users/"));

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