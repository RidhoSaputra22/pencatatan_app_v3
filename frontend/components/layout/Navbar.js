"use client";

import { useAuth } from "@/context/AuthContext";
import Image from "next/image";

export default function Navbar({ onMenuClick }) {
  const { user, logout } = useAuth();
  return (
    <nav className="w-full flex items-center justify-between px-4 py-3 bg-white border-b shadow-sm z-30">
      <div className="flex items-center gap-2">
        <button
          className="lg:hidden p-2 rounded hover:bg-gray-100 focus:outline-none"
          aria-label="Open sidebar menu"
          onClick={() => onMenuClick && onMenuClick(true)}
        >
          <svg
            width="22"
            height="22"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M4 6h16M4 12h16M4 18h16"
            />
          </svg>
        </button>
        <div className="flex gap-4 items-center">
          <Image
            src="/images/logo.png"
            alt="Pencatatan Pengunjung"
            width={100}
            height={100}
            className="w-auto h-10 "
          />
          <span className="font-bold select-none text-primary">
            <p className="text-xl font-bold tracking-wide">
              Pencatatan Pengunjung
            </p>
            <p className="font-light">Universitas Kristen Indonesia Paulus</p>
          </span>
        </div>
      </div>
      <div className="hidden lg:flex items-center gap-6">
        {/* Tambahkan menu/topbar lain di sini jika perlu */}
        {user && (
          <button
            onClick={logout}
            className="px-4 py-2 rounded bg-red-500 text-white hover:bg-red-600 transition"
          >
            Logout
          </button>
        )}
      </div>
    </nav>
  );
}
