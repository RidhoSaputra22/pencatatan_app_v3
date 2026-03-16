"use client";

import { useAuth } from "@/context/AuthContext";
import { useUsers } from "@/hooks/useUsers";
import UserForm from "@/components/users/UserForm";
import UserTable from "@/components/users/UserTable";
import { useState } from "react";
import Alert from "@/components/ui/Alert";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import Heading from "@/components/ui/Heading";
import Paragraph from "@/components/ui/Paragraph";

export default function UsersPage() {
  const { user } = useAuth();
  const { users, loading, error, addUser, editUser, removeUser } = useUsers();
  const [editingUser, setEditingUser] = useState(null);

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

  // Jika sedang edit user, tampilkan hanya form edit user
  if (editingUser) {
    return (
      <>
        <Heading level={1}>Edit Pengguna</Heading>
        <UserForm
          user={editingUser}
          onSaved={async (userId, payload) => {
            await editUser(userId, payload);
            setEditingUser(null);
          }}
          onCancel={() => setEditingUser(null)}
        />
      </>
    );
  }

  // Jika tidak sedang edit, tampilkan form tambah dan tabel user
  return (
    <>
      <Heading level={1}>Kelola Pengguna</Heading>
      <Paragraph>
        Tambah, edit, atau nonaktifkan pengguna sistem. Jumlah pengguna:{" "}
        <strong>{users.length}</strong>
      </Paragraph>

      {error && <Alert variant="error">{error}</Alert>}

      <UserForm onCreated={addUser} />
      <div className="w-[95dvw] lg:w-full overflow-x-auto">
        <UserTable
          users={users}
          onDelete={removeUser}
          onEditClick={setEditingUser}
        />
      </div>
    </>
  );
}
