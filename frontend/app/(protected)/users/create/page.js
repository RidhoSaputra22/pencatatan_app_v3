"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { createUser } from "@/services/user.service";
import UserForm from "@/components/users/UserForm";
import Alert from "@/components/ui/Alert";
import Heading from "@/components/ui/Heading";
import Paragraph from "@/components/ui/Paragraph";

export default function CreateUserPage() {
  const { user } = useAuth();
  const router = useRouter();

  if (user?.role !== "ADMIN") {
    return (
      <>
        <Heading level={1}>Tambah Pengguna</Heading>
        <Alert variant="error">
          Hanya Admin yang bisa mengakses halaman ini.
        </Alert>
      </>
    );
  }

  return (
    <>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Heading level={1}>Tambah Pengguna</Heading>
          <Paragraph>
            Buat akun baru untuk admin atau operator sistem.
          </Paragraph>
        </div>
        <Link href="/users" className="btn btn-ghost w-fit">
          Kembali ke Daftar
        </Link>
      </div>

      <UserForm
        onCreated={async (payload) => {
          await createUser(payload);
          router.push("/users");
        }}
      />
    </>
  );
}
