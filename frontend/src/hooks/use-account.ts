import { getUser } from "@/actions/get-user";
import { User } from "@/interface/user.interface";
import { get } from "@/lib/fetch-client";
import { useEffect, useState } from "react";

export const useAccount = () => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let mounted = true;

    const loadUser = async () => {
      try {
        let result = await getUser();
        // Hosted environments may return a wrapped payload or fail server-action hydration.
        // Fall back to the client proxy route so header identity still renders.
        if (!result) {
          const res = await get<User | { user?: User }>("auth/get-user-config/");
          if (res.data) {
            const maybeWrapped = res.data as { user?: User };
            result = maybeWrapped.user ?? (res.data as User);
          }
        }
        if (mounted) {
          setUser(result);
          setError(null);
        }
      } catch (err) {
        if (mounted) {
          setError(err as Error);
          setUser(null);
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    loadUser();

    return () => {
      mounted = false;
    };
  }, []);

  return { user, loading, error };
};
