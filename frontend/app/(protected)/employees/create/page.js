"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { createEmployee } from "@/services/employee.service";
import EmployeeForm from "@/components/employees/EmployeeForm";
import Alert from "@/components/ui/Alert";
import Heading from "@/components/ui/Heading";
import Paragraph from "@/components/ui/Paragraph";

export default function CreateEmployeePage() {
  const { user } = useAuth();
  const router = useRouter();

  if (user?.role !== "ADMIN") {
    return (
      <>
        <Heading level={1}>Tambah Pegawai</Heading>
        <Alert type="error">Hanya Admin yang bisa mengakses halaman ini.</Alert>
      </>
    );
  }

  return (
    <>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Heading level={1}>Tambah Pegawai</Heading>
          <Paragraph>
            Tambahkan data pegawai baru untuk kebutuhan face registry di edge worker.
          </Paragraph>
        </div>
        <Link href="/employees" className="btn btn-ghost w-fit">
          Kembali ke Daftar
        </Link>
      </div>

      <EmployeeForm
        onCreated={async (formData) => {
          await createEmployee(formData);
          router.push("/employees");
        }}
      />
    </>
  );
}
