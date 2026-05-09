"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

function DashboardIcon() {
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
        d="M3.75 6A2.25 2.25 0 0 1 6 3.75h2.25A2.25 2.25 0 0 1 10.5 6v2.25a2.25 2.25 0 0 1-2.25 2.25H6a2.25 2.25 0 0 1-2.25-2.25V6ZM3.75 15.75A2.25 2.25 0 0 1 6 13.5h2.25a2.25 2.25 0 0 1 2.25 2.25V18a2.25 2.25 0 0 1-2.25 2.25H6A2.25 2.25 0 0 1 3.75 18v-2.25ZM13.5 6a2.25 2.25 0 0 1 2.25-2.25H18A2.25 2.25 0 0 1 20.25 6v2.25A2.25 2.25 0 0 1 18 10.5h-2.25a2.25 2.25 0 0 1-2.25-2.25V6ZM13.5 15.75a2.25 2.25 0 0 1 2.25-2.25H18a2.25 2.25 0 0 1 2.25 2.25V18A2.25 2.25 0 0 1 18 20.25h-2.25A2.25 2.25 0 0 1 13.5 18v-2.25Z"
      />
    </svg>
  );
}
function CameraIcon() {
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
        d="m15.75 10.5 4.72-4.72a.75.75 0 0 1 1.28.53v11.38a.75.75 0 0 1-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25h-9A2.25 2.25 0 0 0 2.25 7.5v9a2.25 2.25 0 0 0 2.25 2.25Z"
      />
    </svg>
  );
}
function UsersIcon() {
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
function EmployeesIcon() {
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
        d="M18 18.72a9.094 9.094 0 0 0 3.741-.479 3 3 0 0 0-4.682-2.72m.94 3.198.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0 1 12 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 0 1 6 18.719m12 0a5.971 5.971 0 0 0-.941-3.197m0 0A5.995 5.995 0 0 0 12 12.75a5.995 5.995 0 0 0-5.058 2.772m0 0a3 3 0 0 0-4.681 2.72 8.986 8.986 0 0 0 3.74.477m.94-3.197a5.971 5.971 0 0 0-.94 3.197M15 6.75a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm6 3a2.25 2.25 0 1 1-4.5 0 2.25 2.25 0 0 1 4.5 0Zm-13.5 0a2.25 2.25 0 1 1-4.5 0 2.25 2.25 0 0 1 4.5 0Z"
      />
    </svg>
  );
}
function VisitsIcon() {
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
        d="M10.5 6a7.5 7.5 0 1 0 7.5 7.5h-7.5V6Z"
      />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M13.5 10.5H21A7.5 7.5 0 0 0 13.5 3v7.5Z"
      />
    </svg>
  );
}
function RecordingsIcon() {
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
        d="M3.375 7.5A1.125 1.125 0 0 1 4.5 6.375h15A1.125 1.125 0 0 1 20.625 7.5v9A1.125 1.125 0 0 1 19.5 17.625h-15A1.125 1.125 0 0 1 3.375 16.5v-9Z"
      />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M8.25 9.375 14.25 12l-6 2.625v-5.25Z"
      />
    </svg>
  );
}
function SettingsIcon() {
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
        d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a7.723 7.723 0 0 1 0 .255c-.007.378.138.75.431.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.02-.397-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.326-.196-.721-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.379-.138-.752-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.127.332-.184.582-.496.644-.87l.214-1.28Z"
      />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"
      />
    </svg>
  );
}

export default function Sidebar({ mobileOpen = false, setMobileOpen }) {
  const { user } = useAuth();
  const pathname = usePathname();
  const isAdmin = user?.role === "ADMIN";

  function isActivePath(href) {
    return pathname === href || pathname.startsWith(`${href}/`);
  }

  function navLink(href, label, children, options = {}) {
    const { nested = false } = options;
    const active = isActivePath(href);
    return (
      <li key={href}>
        <Link
          href={href}
          className={`rounded-md flex items-center gap-3 px-4 py-2.5 transition text-sm${
            nested ? "ml-3 rounded-md  " : "rounded-md"
          } ${
            active
              ? "bg-primary font-semibold text-white shadow-sm"
              : "text-base-content/80 hover:bg-base-200"
          }`}
          onClick={() => setMobileOpen && setMobileOpen(false)}
        >
          {children}
          <span>{label}</span>
        </Link>
      </li>
    );
  }

  function navSection(title, items) {
    return (
      <li key={title} className="mt-5">
        <div className="px-4 pb-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-base-content/40">
            <span>{title}</span>
          </div>
        </div>
        <ul className="space-y-1">{items}</ul>
      </li>
    );
  }

  const navigation = (
    <ul className="flex-1 flex flex-col gap-1">
      {navLink("/dashboard", "Dashboard", <DashboardIcon />)}
      {isAdmin &&
        navSection(
          "Data Master",
          [
            navLink("/camera", "Kamera", <CameraIcon />),
            navLink("/employees", "Pegawai", <EmployeesIcon />),
            navLink("/users", "Pengguna", <UsersIcon />),
          ],
        )}
      {isAdmin &&
        navSection(
          "Laporan Pengunjung",
          [navLink("/visits", "Pengunjung", <VisitsIcon />)],
        )}
      {navSection(
        "Arsip CCTV",
        [navLink("/recordings", "Rekaman CCTV", <RecordingsIcon />)],
      )}
    </ul>
  );

  const MobileSidebar = (
    <div
      className={`fixed inset-0 z-50 bg-black/40 transition-opacity duration-200 ${mobileOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"}`}
      onClick={() => setMobileOpen(false)}
    >
      <aside
        className={`absolute left-0 top-0 h-full w-64 bg-base-100 border-r border-base-300/50 flex flex-col py-6 px-2 min-h-screen shadow-xl transition-transform duration-200 ${mobileOpen ? "translate-x-0" : "-translate-x-full"}`}
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
        <div className="mb-5 px-4">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-base-content/40">
            Navigasi
          </p>
          <p className="mt-2 text-sm text-base-content/50">
            Dashboard, data master, dan laporan pengunjung.
          </p>
        </div>
        {navigation}
      </aside>
    </div>
  );

  const DesktopSidebar = (
    <aside className="hidden lg:flex h-full w-64 bg-base-100 border-r border-base-300/50 flex-col py-6 px-3 sticky top-0 min-h-screen">
      <div className="mb-5 px-4">
      </div>
      {navigation}
    </aside>
  );

  return (
    <>
      {MobileSidebar}
      {DesktopSidebar}
    </>
  );
}
