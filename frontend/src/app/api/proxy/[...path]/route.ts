import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { apiEndpoint } from "@/common/constants/api";
import { AUTHENTICATION_COOKIE } from "@/common/constants/auth-cookie";
import { refreshAuthSession, ensureValidSession } from "@/lib/refresh-session";
import { disabledApiFeature } from "@/lib/features-server";
import { isSameOriginProxyRequest } from "@/lib/proxy-security";

type RouteContext = { params: Promise<{ path: string[] }> };
const NO_STORE_HEADERS = { "Cache-Control": "private, no-store" };

async function forwardToBackend(
  req: NextRequest,
  targetPath: string,
  token: string | undefined
) {
  const normalizedPath = targetPath.endsWith("/") ? targetPath : `${targetPath}/`;
  const url = `${apiEndpoint(normalizedPath)}${req.nextUrl.search}`;

  const headers: Record<string, string> = {};
  const contentType = req.headers.get("content-type");
  if (contentType) {
    headers["Content-Type"] = contentType;
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  const body = hasBody ? await req.text() : undefined;

  return fetch(url, {
    method: req.method,
    headers,
    body,
    cache: "no-store",
  });
}

async function proxyToBackend(req: NextRequest, context: RouteContext) {
  if (!isSameOriginProxyRequest(req.method, req.headers.get("origin"), req.nextUrl.origin)) {
    return NextResponse.json(
      { message: "Cross-origin requests are not allowed." },
      { status: 403, headers: NO_STORE_HEADERS },
    );
  }

  const { path } = await context.params;
  const disabled = await disabledApiFeature(path.join("/"));
  if (disabled) return NextResponse.json(disabled, { status: 403, headers: NO_STORE_HEADERS });
  const cookieStore = await cookies();
  let token = cookieStore.get(AUTHENTICATION_COOKIE)?.value;
  await ensureValidSession();
  token = (await cookies()).get(AUTHENTICATION_COOKIE)?.value;

  const targetPath = path.join("/");

  try {
    let res = await forwardToBackend(req, targetPath, token);

    if (res.status === 401) {
      const refreshed = await refreshAuthSession();
      if (refreshed) {
        token = (await cookies()).get(AUTHENTICATION_COOKIE)?.value;
        res = await forwardToBackend(req, targetPath, token);
      }
    }

    const responseBody = await res.text();
    return new NextResponse(responseBody, {
      status: res.status,
      headers: {
        "Content-Type": res.headers.get("content-type") || "application/json",
        ...NO_STORE_HEADERS,
      },
    });
  } catch {
    return NextResponse.json(
      { message: "Unable to reach the configured API server." },
      { status: 502, headers: NO_STORE_HEADERS }
    );
  }
}

export const GET = proxyToBackend;
export const POST = proxyToBackend;
export const PATCH = proxyToBackend;
export const PUT = proxyToBackend;
export const DELETE = proxyToBackend;
