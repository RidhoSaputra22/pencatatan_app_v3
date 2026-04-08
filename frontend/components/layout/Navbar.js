"use client";

import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import Image from "next/image";

export default function Navbar({ onMenuClick }) {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  return (
    <nav className="w-full flex items-center justify-between px-4 py-3 bg-base-100 border-b border-base-300/50 shadow-sm z-30">
      <div className="flex items-center gap-2">
        <button
          className="lg:hidden p-2 rounded hover:bg-base-200 focus:outline-none"
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
            <p className="font-light text-base-content/60">Universitas Kristen Indonesia Paulus</p>
          </span>
        </div>
      </div>
      <div className="flex items-center gap-3">
        {/* Dark Mode Toggle */}
        <button
          onClick={toggleTheme}
          className="p-2 rounded-lg hover:bg-base-200 transition-colors group"
          aria-label="Toggle dark mode"
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        >
          {theme === "dark" ? (
            <svg className="w-5 h-5 text-yellow-400 group-hover:rotate-45 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          ) : (
            <svg className="w-5 h-5 text-base-content/60 group-hover:text-primary transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            </svg>
          )}
        </button>

        {user && (
          <button
            onClick={logout}
            className="px-4 py-2 rounded bg-red-500 text-white hover:bg-red-600 transition hidden lg:block"
          >
            Logout
          </button>
        )}
      </div>
    </nav>
  );
}
