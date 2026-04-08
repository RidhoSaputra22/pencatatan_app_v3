"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { useState } from "react";
// Contoh icon, ganti sesuai kebutuhan
function DashboardIcon(props) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className="h-5 w-5"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
        d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"
      ></path>
    </svg>
  );
}
function CameraIcon(props) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth="1.5"
      stroke="currentColor"
      className="size-6"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M6.827 6.175A2.31 2.31 0 0 1 5.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 0 0 2.25 2.25h15A2.25 2.25 0 0 0 21.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 0 0-1.134-.175 2.31 2.31 0 0 1-1.64-1.055l-.822-1.316a2.192 2.192 0 0 0-1.736-1.039 48.774 48.774 0 0 0-5.232 0 2.192 2.192 0 0 0-1.736 1.039l-.821 1.316Z"
      />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M16.5 12.75a4.5 4.5 0 1 1-9 0 4.5 4.5 0 0 1 9 0ZM18.75 10.5h.008v.008h-.008V10.5Z"
      />
    </svg>
  );
}
function UsersIcon(props) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth="1.5"
      stroke="currentColor"
      className="size-6"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M15 19.128a9.38 9.38 0 0 0 2.625.372 9.337 9.337 0 0 0 4.121-.952 4.125 4.125 0 0 0-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 0 1 8.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0 1 11.964-3.07M12 6.375a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0Zm8.25 2.25a2.625 2.625 0 1 1-5.25 0 2.625 2.625 0 0 1 5.25 0Z"
      />
    </svg>
  );
}
function EmployeesIcon(props) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth="1.5"
      stroke="currentColor"
      className="size-6"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M15.75 5.25a3 3 0 1 1-6 0 3 3 0 0 1 6 0ZM4.5 20.118a7.5 7.5 0 0 1 15 0A17.933 17.933 0 0 1 12 21.75a17.933 17.933 0 0 1-7.5-1.632Z"
      />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M18.75 8.25h2.25m0 0v2.25m0-2.25L17.25 12"
      />
    </svg>
  );
}
function VisitsIcon(props) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth="1.5"
      stroke="currentColor"
      className="size-6"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3.75 3v11.25A2.25 2.25 0 0 0 6 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0 1 18 16.5h-2.25m-7.5 0h7.5m-7.5 0-1 3m8.5-3 1 3m0 0 .5 1.5m-.5-1.5h-9.5m0 0-.5 1.5m.75-9 3-3 2.148 2.148A12.061 12.061 0 0 1 16.5 7.605"
      ></path>
    </svg>
  );
}

export default function Sidebar({ mobileOpen = false, setMobileOpen }) {
  const { user } = useAuth();
  const pathname = usePathname();
  const isAdmin = user?.role === "ADMIN";

  function navLink(href, label, children) {
    const active = pathname === href;
    return (
      <li key={href}>
        <Link
          href={href}
          className={`flex items-center gap-2 px-4 py-2 rounded hover:bg-gray-200 transition ${active ? "bg-blue-100 font-bold text-blue-700" : "text-gray-700"}`}
          onClick={() => setMobileOpen && setMobileOpen(false)}
        >
          {children}
          <span>{label}</span>
        </Link>
      </li>
    );
  }

  // Mobile sidebar overlay and drawer
  const MobileSidebar = (
    <div
      className={`fixed inset-0 z-50 bg-black/40 transition-opacity duration-200 ${mobileOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"}`}
      onClick={() => setMobileOpen(false)}
    >
      <aside
        className={`absolute left-0 top-0 h-full w-64 bg-white border-r border-gray-200 flex flex-col py-6 px-2 min-h-screen shadow-xl transition-transform duration-200 ${mobileOpen ? "translate-x-0" : "-translate-x-full"}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-8 px-4 flex items-center justify-between">
          <Link
            href="/dashboard"
            className="text-xl font-bold text-success"
            onClick={() => setMobileOpen(false)}
          >
            Pencatatan Pengunjung
          </Link>
          <button
            className="ml-2"
            aria-label="Close sidebar"
            onClick={() => setMobileOpen(false)}
          >
            <svg
              width="24"
              height="24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
        <ul className="flex-1 flex flex-col gap-1">
          {navLink("/dashboard", "Dashboard", <DashboardIcon />)}
          {navLink("/camera", "Kamera", <CameraIcon />)}
          {isAdmin && navLink("/employees", "Pegawai", <EmployeesIcon />)}
          {isAdmin && navLink("/users", "Pengguna", <UsersIcon />)}
          {isAdmin && navLink("/visits", "Data Kunjungan", <VisitsIcon />)}
        </ul>
      </aside>
    </div>
  );

  // Desktop sidebar
  const DesktopSidebar = (
    <aside className="hidden lg:flex h-full w-56 bg-white border-r border-gray-200 flex-col py-6 px-2 sticky top-0 min-h-screen">
   
      <ul className="flex-1 flex flex-col gap-1">
        {navLink("/dashboard", "Dashboard", <DashboardIcon />)}
        {navLink("/camera", "Kamera", <CameraIcon />)}
        {isAdmin && navLink("/employees", "Pegawai", <EmployeesIcon />)}
        {isAdmin && navLink("/users", "Pengguna", <UsersIcon />)}
        {isAdmin && navLink("/visits", "Data Kunjungan", <VisitsIcon />)}
      </ul>
    </aside>
  );

  return (
    <>
      {MobileSidebar}
      {DesktopSidebar}
    </>
  );
}
