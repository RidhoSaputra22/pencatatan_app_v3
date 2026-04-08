"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { fetchEmployees, updateEmployee } from "@/services/employee.service";
import EmployeeForm from "@/components/employees/EmployeeForm";
import Alert from "@/components/ui/Alert";
import Heading from "@/components/ui/Heading";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import Paragraph from "@/components/ui/Paragraph";

export default function EditEmployeePage() {
  const { user } = useAuth();
  const params = useParams();
  const router = useRouter();
  const employeeId = params?.employeeId;
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function loadEmployee() {
      setLoading(true);
      setError("");

      try {
        const data = await fetchEmployees();
        if (!active) return;

        const currentEmployee = data.find(
          (item) => String(item.employee_id) === String(employeeId),
        );

        if (!currentEmployee) {
          setError("Pegawai yang ingin diedit tidak ditemukan.");
          setSelectedEmployee(null);
          return;
        }

        setSelectedEmployee(currentEmployee);
      } catch (e) {
        if (!active) return;
        setError(e.message || "Gagal memuat data pegawai.");
        setSelectedEmployee(null);
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    loadEmployee();
    return () => {
      active = false;
    };
  }, [employeeId]);

  if (user?.role !== "ADMIN") {
    return (
      <>
        <Heading level={1}>Edit Pegawai</Heading>
        <Alert type="error">Hanya Admin yang bisa mengakses halaman ini.</Alert>
      </>
    );
  }

  if (loading) {
    return <LoadingSpinner text="Memuat data pegawai..." />;
  }

  return (
    <>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Heading level={1}>Edit Pegawai</Heading>
          <Paragraph>
            Perbarui data pegawai dan foto referensi wajah bila diperlukan.
          </Paragraph>
        </div>
        <Link href="/employees" className="btn btn-ghost w-fit">
          Kembali ke Daftar
        </Link>
      </div>

      {error && <Alert type="error">{error}</Alert>}

      {selectedEmployee && (
        <EmployeeForm
          employee={selectedEmployee}
          onSaved={async (employeeId, formData) => {
            await updateEmployee(employeeId, formData);
            router.push("/employees");
          }}
          onCancel={() => router.push("/employees")}
        />
      )}
    </>
  );
}
