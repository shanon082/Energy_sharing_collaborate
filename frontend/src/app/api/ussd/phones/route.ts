import { NextResponse } from "next/server";
import { API_URL } from "@/common/constants/api";
import { requireUssdAuthHeaders } from "@/lib/ussd-api-auth";
import { disabledFeature } from "@/lib/features-server";

export async function GET() {
  const disabled = await disabledFeature("ussd");
  if (disabled) return NextResponse.json(disabled, { status: 403 });
  const authHeaders = await requireUssdAuthHeaders();
  if (!authHeaders) {
    return NextResponse.json(
      { ok: false, results: [], error: "Sign in to use the USSD simulator." },
      { status: 401 },
    );
  }

  try {
    const backendResponse = await fetch(`${API_URL}/ussd/phones/`, {
      method: "GET",
      headers: authHeaders,
      cache: "no-store",
    });

    const data = await backendResponse.json();
    if (backendResponse.status === 403 && data?.code === "FEATURE_DISABLED") {
      return NextResponse.json(data, { status: 403 });
    }
    return NextResponse.json(
      {
        ok: backendResponse.ok,
        results: data?.results ?? [],
        error: backendResponse.ok ? undefined : data?.detail,
      },
      { status: backendResponse.ok ? 200 : backendResponse.status },
    );
  } catch (error) {
    return NextResponse.json(
      { ok: false, results: [], error: `Failed to load phone numbers: ${String(error)}` },
      { status: 500 },
    );
  }
}
