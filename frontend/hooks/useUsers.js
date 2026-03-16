"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchUsers, createUser, updateUser, deleteUser } from "@/services/user.service";

/**
 * Hook for user management (admin only).
 */
export function useUsers() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const data = await fetchUsers();
      setUsers(data);
    } catch (e) {
      setError(e.message || "Gagal memuat data pengguna");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const addUser = useCallback(async (data) => {
    const result = await createUser(data);
    await load();
    return result;
  }, [load]);

  const editUser = useCallback(async (userId, data) => {
    const result = await updateUser(userId, data);
    await load();
    return result;
  }, [load]);

  const removeUser = useCallback(async (userId) => {
    const result = await deleteUser(userId);
    await load();
    return result;
  }, [load]);

  return { users, loading, error, reload: load, addUser, editUser, removeUser };
}
