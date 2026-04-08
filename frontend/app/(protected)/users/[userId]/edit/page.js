"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { fetchUsers, updateUser } from "@/services/user.service";
import UserForm from "@/components/users/UserForm";
import Alert from "@/components/ui/Alert";
import Heading from "@/components/ui/Heading";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import Paragraph from "@/components/ui/Paragraph";

export default function EditUserPage() {
  const { user } = useAuth();
  const params = useParams();
  const router = useRouter();
  const userId = params?.userId;
  const [selectedUser, setSelectedUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function loadUser() {
      setLoading(true);
      setError("");

      try {
        const data = await fetchUsers();
        if (!active) return;

        const currentUser = data.find(
          (item) => String(item.user_id) === String(userId),
        );

        if (!currentUser) {
          setError("Pengguna yang ingin diedit tidak ditemukan.");
          setSelectedUser(null);
          return;
        }

        setSelectedUser(currentUser);
      } catch (e) {
        if (!active) return;
        setError(e.message || "Gagal memuat data pengguna.");
        setSelectedUser(null);
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    loadUser();
    return () => {
      active = false;
    };
  }, [userId]);

  if (user?.role !== "ADMIN") {
    return (
      <>
        <Heading level={1}>Edit Pengguna</Heading>
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
          <Heading level={1}>Edit Pengguna</Heading>
          <Paragraph>
            Perbarui informasi akun pengguna yang dipilih.
          </Paragraph>
        </div>
        <Link href="/users" className="btn btn-ghost w-fit">
          Kembali ke Daftar
        </Link>
      </div>

      {error && <Alert variant="error">{error}</Alert>}

      {selectedUser && (
        <UserForm
          user={selectedUser}
          onSaved={async (userId, payload) => {
            await updateUser(userId, payload);
            router.push("/users");
          }}
          onCancel={() => router.push("/users")}
        />
      )}
    </>
  );
}
