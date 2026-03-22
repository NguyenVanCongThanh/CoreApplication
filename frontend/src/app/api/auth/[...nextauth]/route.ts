import { NextAuthOptions } from "next-auth";
import NextAuth from "next-auth/next";
import CredentialsProvider from "next-auth/providers/credentials";

declare module "next-auth" {
  interface Session {
    accessToken?: string;
    error?: string;
    user: {
      /** Existing default fields */
      name?: string | null;
      email?: string | null;
      role?: string;
    };
  }

  interface User {
    role?: string;
    token?: string;
  }

  interface JWT {
    role?: string;
    accessToken?: string;
    refreshToken?: string;
    accessTokenExpires?: number;
    error?: string;
  }
}

async function refreshAccessToken(token: any) {
  try {
    const response = await fetch(`${process.env.BACKEND_URL}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refreshToken: token.refreshToken }),
    });

    if (!response.ok) {
        throw new Error("Refresh failed");
    }

    const data = await response.json();
    
    // Extract cookies
    const setCookie = response.headers.get("set-cookie");
    const authToken = setCookie?.match(/authToken=([^;]+)/)?.[1];
    const refreshToken = setCookie?.match(/refreshToken=([^;]+)/)?.[1];

    return {
      ...token,
      accessToken: authToken || token.accessToken,
      accessTokenExpires: Date.now() + data.expiresIn,
      refreshToken: refreshToken || token.refreshToken,
    };
  } catch (error) {
    console.error("RefreshAccessTokenError", error);
    return {
      ...token,
      error: "RefreshAccessTokenError",
    };
  }
}

export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: "Credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          return null;
        }

        try {
          const res = await fetch(`${process.env.BACKEND_URL}/api/auth/login`, {
            method: "POST",
            body: JSON.stringify({
              email: credentials.email,
              password: credentials.password,
            }),
            headers: { "Content-Type": "application/json" },
          });

          if (!res.ok) {
            return null;
          }
          
          const data = await res.json();
          const setCookie = res.headers.get("set-cookie");
          const authToken = setCookie?.match(/authToken=([^;]+)/)?.[1];
          const refreshToken = setCookie?.match(/refreshToken=([^;]+)/)?.[1];

          return {
            id: data.email,
            name: data.name,
            email: data.email,
            role: data.role,
            token: authToken,
            refreshToken: refreshToken,
            expiresIn: data.expiresIn,
          };
        } catch {
          return null;
        }
      },
    }),
  ],
  session: {
    strategy: "jwt",
    maxAge: 7 * 24 * 60 * 60, // 7 days (NextAuth session can live longer because we refresh the underlying JWT)
  },
  callbacks: {
    async jwt({ token, user, account }) {
      // Initial sign in
      if (user && account) {
        return {
          accessToken: (user as any).token,
          refreshToken: (user as any).refreshToken,
          accessTokenExpires: Date.now() + ((user as any).expiresIn || 3600000),
          role: user.role,
          user: {
             name: user.name,
             email: user.email,
          }
        };
      }

      // Return previous token if the access token has not expired yet
      // We refresh 5 minutes before actual expiry to be safe
      if (Date.now() < (token as any).accessTokenExpires - 300000) {
        return token;
      }

      // Access token has expired, try to update it
      return refreshAccessToken(token);
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.role = token.role as string;
        (session as any).error = token.error;
      }
      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
  secret: process.env.NEXTAUTH_SECRET,
};

const handler = NextAuth(authOptions);

export { handler as GET, handler as POST };