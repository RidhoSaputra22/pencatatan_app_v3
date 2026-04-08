"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/services/auth.service";
import { useAuth } from "@/context/AuthContext";
import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";
import Alert from "@/components/ui/Alert";
import Image from "next/image";

export default function LoginPage() {
  const router = useRouter();
  const { login: authLogin } = useAuth();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      const data = await login(username, password);
      authLogin(data.access_token);
      router.push("/dashboard");
    } catch (e2) {
      setErr("Login gagal, cek kembali username dan password");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-base-200">
      <div className="card bg-base-100 shadow-xl w-full max-w-md p-8">
        <div className="flex gap-3">
          <Image
            src="/images/logo.png"
            alt="Pencatatan Pengunjung"
            width={100}
            height={100}
            className="w-auto h-14 mb-4"
          />
          <div>
            <h1 className="text-2xl font-bold ">Pencatatan Pengunjung</h1>
            <p className="text-sm opacity-60 mb-6">
              Login untuk mengakses dashboard
            </p>
          </div>
        </div>
        <form onSubmit={onSubmit} className="grid gap-4">
          <Input
            label="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoFocus
          />
          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <Button variant="primary" loading={loading} className="w-full">
            Masuk
          </Button>
          {err && <Alert variant="error">{err}</Alert>}
        </form>
      </div>
    </div>
  );
}
