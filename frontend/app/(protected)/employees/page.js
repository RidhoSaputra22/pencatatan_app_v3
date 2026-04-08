"use client";

import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import EmployeeTable from "@/components/employees/EmployeeTable";
import Alert from "@/components/ui/Alert";
import Heading from "@/components/ui/Heading";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import Paragraph from "@/components/ui/Paragraph";
import { useEmployees } from "@/hooks/useEmployees";

export default function EmployeesPage() {
  const { user } = useAuth();
  const {
    employees,
    loading,
    error,
    removeEmployee,
  } = useEmployees();

  if (user?.role !== "ADMIN") {
    return (
      <>
        <Heading level={1}>Kelola Pegawai</Heading>
        <Alert type="error">Hanya Admin yang bisa mengakses halaman ini.</Alert>
      </>
    );
  }

  if (loading) {
    return <LoadingSpinner text="Memuat data pegawai..." />;
  }

  const activeEmployees = employees.filter((employee) => employee.is_active).length;

  return (
    <>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Heading level={1}>Kelola Pegawai</Heading>
          <Paragraph>
            Data pegawai digunakan edge worker untuk memeriksa wajah dan
            mengabaikan pegawai dari hitungan pelanggan. Pegawai aktif:{" "}
            <strong>{activeEmployees}</strong> dari <strong>{employees.length}</strong>.
            
          </Paragraph>
        </div>
        <Link href="/employees/create" className="btn btn-primary w-fit">
          Tambah Pegawai
        </Link>
      </div>

      {error && <Alert type="error">{error}</Alert>}

      <div className="w-[95dvw] lg:w-full overflow-x-auto">
        <EmployeeTable employees={employees} onDelete={removeEmployee} />
      </div>
    </>
  );
}
