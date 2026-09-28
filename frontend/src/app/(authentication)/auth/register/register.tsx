"use server"

import { get, post } from "@/lib/fetch";
import { getApiErrorMessage } from "@/lib/api-response";
import { createAccountSchema } from "@/lib/schema";
import { z } from "zod";

export default async function createUser(data: z.infer<typeof createAccountSchema>){
  try {
    const { error } = await post("auth/register/", data);

    if(error){
      return { error: getApiErrorMessage(error, "Registration failed") }
    }

    return {
      success: true,
      email: data.email,
      message: "Account created successfully.",
    };

  } catch (error) {
    console.error("Registration error:", error);
    return { error: "An unexpected error occurred during registration" };
  }
}

export async function getUserByRefCode<T>(refCode: string){
  const response = await get(`auth/get-user-sponsor/${refCode}`);
  if (response.error) {
    throw new Error(getApiErrorMessage(response.error, "Failed to fetch user by referral code"));
  }
  return response.data as T;
}
