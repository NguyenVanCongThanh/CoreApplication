import Footer from "@/components/layout/Footer";
import MobileNav from "@/components/layout/MobileNav";
import Sidebar from "@/components/layout/Sidebar";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

type MainLayoutProps = {
  children: React.ReactNode;
};

export default async function MainLayout({ children }: MainLayoutProps) {
  const cookieStore = await cookies();
  const token = cookieStore.get("authToken")?.value;
  if (!token) redirect("/");

  return (
    <div className="flex min-h-screen w-screen flex-col bg-slate-50 dark:bg-slate-950">
      {/* Row: sidebar (sticky) + content */}
      <div className="flex flex-1">
        <div className="sticky top-0 h-screen flex-shrink-0 hidden md:block">
          <Sidebar />
        </div>

        <div className="flex flex-1 flex-col min-w-0">
          <div className="sticky top-0 z-40 md:hidden">
            <MobileNav />
          </div>
          <main className="flex-1 p-4 sm:p-6 lg:p-8">
            {children}
          </main>
        </div>
      </div>

      {/* Full-width footer — chỉ thấy khi scroll xuống cuối */}
      <Footer />
    </div>
  );
}