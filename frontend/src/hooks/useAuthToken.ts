"use client";
import { useState, useEffect } from 'react';

export function useAuthToken() {
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const extractToken = () => {
      try {
        // Try to get token from cookies
        const cookies = document.cookie.split('; ');
        const authCookie = cookies.find(cookie => 
          cookie.startsWith('AUTHENTICATION_COOKIE=')
        );
        
        if (authCookie) {
          const tokenValue = authCookie.split('=')[1];
          setToken(tokenValue);
        } else {
          // Try localStorage as fallback
          const storedToken = localStorage.getItem('authToken');
          if (storedToken) {
            setToken(storedToken);
          } else {
            setToken(null);
          }
        }
      } catch (error) {
        console.error('Error extracting token:', error);
        setToken(null);
      }
      setIsLoading(false);
    };

    extractToken();

    // Listen for storage changes
    const handleStorageChange = () => extractToken();
    window.addEventListener('storage', handleStorageChange);
    
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  return { token, isLoading };
}