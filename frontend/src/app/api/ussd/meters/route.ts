import { NextRequest, NextResponse } from "next/server";
import { API_URL } from "@/common/constants/api";
import { requireUssdAuthHeaders } from "@/lib/ussd-api-auth";

export async function GET(_request: NextRequest) {
  const authHeaders = await requireUssdAuthHeaders();
  if (!authHeaders) {
    return NextResponse.json(
      { ok: false, results: [], error: "Sign in to use the USSD simulator." },
      { status: 401 },
    );
  }

  try {
    const backendResponse = await fetch(`${API_URL}/ussd/meters/`, {
      method: "GET",
      headers: authHeaders,
      cache: "no-store",
    });

    const data = await backendResponse.json();
    return NextResponse.json(
      {
        ok: backendResponse.ok,
        results: data?.results ?? [],
      },
      { status: backendResponse.ok ? 200 : backendResponse.status },
    );
  } catch (error) {
    return NextResponse.json(
      { ok: false, results: [], error: `Failed to load meter numbers: ${String(error)}` },
      { status: 500 },
    );
  }
}
