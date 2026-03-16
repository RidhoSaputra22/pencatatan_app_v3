"use client";

import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import EmployeeForm from "@/components/employees/EmployeeForm";
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
    addEmployee,
    editEmployee,
    removeEmployee,
  } = useEmployees();
  const [editingEmployee, setEditingEmployee] = useState(null);

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

  if (editingEmployee) {
    return (
      <>
        <Heading level={1}>Edit Pegawai</Heading>
        <EmployeeForm
          employee={editingEmployee}
          onSaved={async (employeeId, formData) => {
            await editEmployee(employeeId, formData);
            setEditingEmployee(null);
          }}
          onCancel={() => setEditingEmployee(null)}
        />
      </>
    );
  }

  const activeEmployees = employees.filter((employee) => employee.is_active).length;

  return (
    <>
      <Heading level={1}>Kelola Pegawai</Heading>
      <Paragraph>
        Data pegawai di halaman ini digunakan edge worker untuk memeriksa wajah dan
        mengabaikan pegawai dari hitungan pelanggan. Pegawai aktif:{" "}
        <strong>{activeEmployees}</strong> dari <strong>{employees.length}</strong>.
      </Paragraph>

      {error && <Alert type="error">{error}</Alert>}

      <EmployeeForm onCreated={addEmployee} />
      <div className="w-[95dvw] lg:w-full overflow-x-auto">
        <EmployeeTable
          employees={employees}
          onDelete={removeEmployee}
          onEditClick={setEditingEmployee}
        />
      </div>
    </>
  );
}
