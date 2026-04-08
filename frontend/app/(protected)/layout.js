"use client";

import Sidebar from "@/components/layout/Sidebar";
import AuthGuard from "@/components/layout/AuthGuard";
import Navbar from "@/components/layout/Navbar";
import { useState } from "react";


/**
 * Layout for all protected (authenticated) pages.
 * Wraps children with AuthGuard + Navbar.
 */
export default function ProtectedLayout({ children }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const currentYear = new Date().getFullYear();

  return (
    <AuthGuard>
      <div className="flex flex-col min-h-screen bg-base-200/30">
        <Navbar onMenuClick={setSidebarOpen} />
        <div className="flex flex-1 min-h-0">
          <Sidebar mobileOpen={sidebarOpen} setMobileOpen={setSidebarOpen} />
          <main className="flex flex-1 min-h-screen flex-col px-3 py-6 sm:px-4 lg:px-8 lg:py-8">
            <div className="flex-1">{children}</div>
            <footer className="mt-10 border-t border-base-300/40 pt-4 text-center text-xs text-base-content/40">
              © {currentYear} Pencatatan Pengunjung. Universitas Kristen
              Indonesia Paulus.
            </footer>
          </main>
        </div>
      </div>
    </AuthGuard>
  );
}
