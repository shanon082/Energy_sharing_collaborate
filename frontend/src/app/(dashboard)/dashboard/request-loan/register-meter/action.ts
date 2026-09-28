'use server';

import { post } from "@/lib/fetch";
import { getApiErrorMessage } from "@/lib/api-response";

export async function registerMeter(formData: {
  meter_no: string;
  architecture: "STS" | "AMI";
  static_ip?: string;
  label?: string;
}) {
    try {
        const response = await post<any>('meter/register/', formData);

        if (response.error) {
            return {
                error: getApiErrorMessage(response.error, "Failed to register meter"),
            };
        }

        return { success: "Meter registered successfully!", data: response.data };
    } catch (err: any) {
        if (err.message?.includes('Network Error') || err.message?.includes('Failed to fetch')) {
            return { error: "Network error. Please check your connection and try again." };
        }

        if (err.status === 401) {
            return { error: "Please log in to register a meter." };
        }

        if (err.status === 400) {
            return { error: err.message || "Invalid meter data. Please check your inputs." };
        }

        return { error: "Failed to register meter. Please try again." };
    }
}
