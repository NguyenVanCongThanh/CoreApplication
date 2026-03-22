import { NextRequest, NextResponse } from "next/server";
import { getToken } from "next-auth/jwt";

export async function GET(req: NextRequest) {
  const tokenData = await getToken({
    req,
    secret: process.env.NEXTAUTH_SECRET,
  });
  
  const token = tokenData?.accessToken ?? null;

  return NextResponse.json(
    { token },
    {
      headers: {
        "Cache-Control": "no-store, no-cache, must-revalidate",
      },
    }
  );
}