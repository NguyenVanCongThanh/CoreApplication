import Footer from "@/components/layout/Footer";
import { redirect } from "next/navigation";
import { cookies } from "next/headers";

type DashboardLayoutProps = {
  children: React.ReactNode;
};

export default async function DashboardLayout({ children }: DashboardLayoutProps) {
  const cookieStore = await cookies();
  const token = cookieStore.get("authToken")?.value;
  if (token) {
    redirect("/");
  }

  return (
    <div className="relative min-h-screen flex flex-col bg-slate-50 text-slate-900 font-sans">
      <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex flex-col">
        {children}
      </main>

      <Footer />
    </div>
  );
}