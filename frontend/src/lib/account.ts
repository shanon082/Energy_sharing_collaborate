import { get } from "@/lib/fetch";

export const getUserConfig = async <T>(): Promise<T | null> => {
  try {
    const response = await get<T>("auth/get-user-config/");
    if (response.error || !response.data) {
      return null;
    }
    return response.data;
  } catch {
    return null;
  }
};
