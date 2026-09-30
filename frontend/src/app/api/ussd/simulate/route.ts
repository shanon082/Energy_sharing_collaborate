import { NextRequest, NextResponse } from "next/server";
import { API_URL } from "@/common/constants/api";
import { requireUssdAuthHeaders } from "@/lib/ussd-api-auth";
import { disabledFeature } from "@/lib/features-server";

type UssdPayload = {
  sessionId: string;
  serviceCode: string;
  phoneNumber: string;
  text: string;
};

export async function POST(request: NextRequest) {
  const disabled = await disabledFeature("ussd");
  if (disabled) return NextResponse.json(disabled, { status: 403 });
  const authHeaders = await requireUssdAuthHeaders();
  if (!authHeaders) {
    return NextResponse.json(
      { ok: false, error: "Sign in to use the USSD simulator." },
      { status: 401 },
    );
  }

  try {
    const body = (await request.json()) as UssdPayload;
    const endpoint = `${API_URL}/ussd/entry/`;

    const backendResponse = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders },
      body: JSON.stringify(body),
      cache: "no-store",
    });

    const raw = await backendResponse.text();
    if (backendResponse.status === 403) {
      try {
        const body = JSON.parse(raw);
        if (body?.code === "FEATURE_DISABLED") {
          return NextResponse.json(body, { status: 403 });
        }
      } catch {
        // The USSD gateway can also return plain text; preserve that below.
      }
    }
    let normalized = raw.trim();

    if (normalized.startsWith('"') && normalized.endsWith('"')) {
      try {
        normalized = JSON.parse(normalized);
      } catch {
        normalized = normalized.slice(1, -1);
      }
    }

    return NextResponse.json(
      {
        ok: backendResponse.ok,
        status: backendResponse.status,
        response: normalized,
      },
      { status: backendResponse.ok ? 200 : backendResponse.status },
    );
  } catch (error) {
    return NextResponse.json(
      { ok: false, error: `Simulator request failed: ${String(error)}` },
      { status: 500 },
    );
  }
}
