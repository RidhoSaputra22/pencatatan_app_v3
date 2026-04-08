"use client";

import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { useUsers } from "@/hooks/useUsers";
import UserTable from "@/components/users/UserTable";
import Alert from "@/components/ui/Alert";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import Heading from "@/components/ui/Heading";
import Paragraph from "@/components/ui/Paragraph";

export default function UsersPage() {
  const { user } = useAuth();
  const { users, loading, error, removeUser } = useUsers();

  // Only admin can access this page
  if (user?.role !== "ADMIN") {
    return (
      <>
        <Heading level={1}>Kelola Pengguna</Heading>
        <Alert variant="error">
          Hanya Admin yang bisa mengakses halaman ini.
        </Alert>
      </>
    );
  }

  if (loading) {
    return <LoadingSpinner text="Memuat data pengguna..." />;
  }
  return (
    <>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Heading level={1}>Kelola Pengguna</Heading>
          <Paragraph>
            Kelola daftar pengguna sistem. Jumlah pengguna:{" "}
            <strong>{users.length}</strong>
          </Paragraph>
        </div>
        <Link href="/users/create" className="btn btn-primary w-fit">
          Tambah Pengguna
        </Link>
      </div>

      {error && <Alert variant="error">{error}</Alert>}

      <div className="w-[95dvw] lg:w-full overflow-x-auto">
        <UserTable users={users} onDelete={removeUser} />
      </div>
    </>
  );
}
