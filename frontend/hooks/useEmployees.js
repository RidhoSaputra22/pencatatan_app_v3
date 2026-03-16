"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createEmployee,
  deleteEmployee,
  fetchEmployees,
  updateEmployee,
} from "@/services/employee.service";

export function useEmployees() {
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchEmployees();
      setEmployees(data);
    } catch (e) {
      setError(e.message || "Gagal memuat data pegawai");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const addEmployee = useCallback(
    async (formData) => {
      const result = await createEmployee(formData);
      await load();
      return result;
    },
    [load],
  );

  const editEmployee = useCallback(
    async (employeeId, formData) => {
      const result = await updateEmployee(employeeId, formData);
      await load();
      return result;
    },
    [load],
  );

  const removeEmployee = useCallback(
    async (employeeId) => {
      const result = await deleteEmployee(employeeId);
      await load();
      return result;
    },
    [load],
  );

  return {
    employees,
    loading,
    error,
    reload: load,
    addEmployee,
    editEmployee,
    removeEmployee,
  };
}
