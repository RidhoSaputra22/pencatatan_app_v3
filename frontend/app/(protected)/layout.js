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
  return (
    <AuthGuard>
      <div className="flex flex-col min-h-screen bg-gray-50">
        <Navbar onMenuClick={setSidebarOpen} />
        <div className="flex flex-1 min-h-0">
          <Sidebar mobileOpen={sidebarOpen} setMobileOpen={setSidebarOpen} />
          <main className="flex-1 min-h-screen px-2 sm:px-4 lg:px-6 py-8">
            {children}
          </main>
        </div>
      </div>
    </AuthGuard>
  );
}
