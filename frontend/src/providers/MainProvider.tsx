"use client";

import { SessionProvider, useSession, signOut } from "next-auth/react";
import { useEffect, ReactNode } from "react";
import { ThemeProvider } from "next-themes";
import { Toaster } from "react-hot-toast";
import { UserProvider, useUser } from "@/store/UserContext";

function SessionMonitor() {
  const { data: session } = useSession();
  const { setUser } = useUser();

  useEffect(() => {
    if (session?.error === "RefreshAccessTokenError") {
      signOut({ callbackUrl: "/login" });
    }
    
    // Periodically update local context from session if needed
    if (session?.user && session.accessToken) {
       // setUser({ ... }) if necessary to keep sync
    }
  }, [session, setUser]);

  return null;
}

export default function Providers({ children }: { children: ReactNode }) {
  return (
    <UserProvider>
      <SessionProvider refetchInterval={5 * 60}>
        <SessionMonitor />
        <ThemeProvider
          attribute="class"
          defaultTheme="light"
          enableSystem={false}
          storageKey="bdc-theme"
        >
          {children}
          <Toaster />
        </ThemeProvider>
      </SessionProvider>
    </UserProvider>
  );
}