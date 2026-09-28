"use client";

import { ApiResponse, toApiError } from "./api-response";

/** Same-origin proxy — forwards requests with the httpOnly auth cookie server-side. */
const CLIENT_API_BASE = "/api/proxy";

const parseResponseBody = async (res: Response): Promise<unknown> => {
  const contentType = res.headers.get("content-type");

  if (contentType?.includes("application/json")) {
    try {
      return await res.json();
    } catch {
      return undefined;
    }
  }

  const text = await res.text();
  if (!text) {
    return undefined;
  }

  if (contentType?.includes("text/html") || text.trimStart().startsWith("<!DOCTYPE")) {
    return { message: text };
  }

  return { message: text };
};

const buildErrorResponse = (body: unknown, status: number): ApiResponse<never> => ({
  error: toApiError(body, `Request failed with status ${status}`),
  status,
});

const buildSuccessResponse = <T>(body: unknown, status: number): ApiResponse<T> => ({
  data: body as T,
  status,
});

const buildRequestOptions = (
  method?: "POST" | "PATCH" | "PUT" | "DELETE",
  body?: unknown
): RequestInit => {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (!method) {
    return {
      headers,
      credentials: "include",
      cache: "no-store",
    };
  }

  return {
    method,
    headers,
    credentials: "include",
    body: body === undefined ? undefined : JSON.stringify(body),
  };
};

const request = async <T>(
  path: string,
  options: RequestInit,
  allowRefresh = true
): Promise<ApiResponse<T>> => {
  try {
    let res = await fetch(`${CLIENT_API_BASE}/${path}`, options);
    let parsedBody = await parseResponseBody(res);

    if (res.status === 401 && allowRefresh) {
      const refreshRes = await fetch("/api/auth/refresh", {
        method: "POST",
        credentials: "include",
        cache: "no-store",
      });
      if (refreshRes.ok) {
        res = await fetch(`${CLIENT_API_BASE}/${path}`, options);
        parsedBody = await parseResponseBody(res);
      } else if (typeof window !== "undefined") {
        window.location.href = "/auth/login?session=expired";
        return buildErrorResponse({ message: "Session expired" }, 401);
      }
    }

    if (!res.ok) {
      return buildErrorResponse(parsedBody, res.status);
    }

    return buildSuccessResponse<T>(parsedBody, res.status);
  } catch {
    return {
      error: { message: "Network error occurred" },
      status: 0,
    };
  }
};

export const get = async <T>(path: string): Promise<ApiResponse<T>> => {
  return request<T>(path, buildRequestOptions());
};

export const post = async <T, B = unknown>(path: string, data: B): Promise<ApiResponse<T>> => {
  return request<T>(path, buildRequestOptions("POST", data));
};

export const patch = async <T = unknown, B = unknown>(
  path: string,
  data: B
): Promise<ApiResponse<T>> => {
  return request<T>(path, buildRequestOptions("PATCH", data));
};

export const put = async <T, B = unknown>(path: string, data: B): Promise<ApiResponse<T>> => {
  return request<T>(path, buildRequestOptions("PUT", data));
};

export const del = async <T = unknown>(path: string): Promise<ApiResponse<T>> => {
  return request<T>(path, buildRequestOptions("DELETE"));
};
