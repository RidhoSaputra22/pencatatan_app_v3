"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/services/auth.service";
import { useAuth } from "@/context/AuthContext";
import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";
import Alert from "@/components/ui/Alert";

export default function LoginPage() {
  const router = useRouter();
  const { login: authLogin } = useAuth();

  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123");
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
      setErr(e2.message || "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-base-200">
      <div className="card bg-base-100 shadow-xl w-full max-w-md p-8">
        <h1 className="text-2xl font-bold text-success mb-1">Visitor Monitoring</h1>
        <p className="text-sm opacity-60 mb-6">Login untuk mengakses dashboard</p>

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
            Sign in
          </Button>
          {err && <Alert variant="error">{err}</Alert>}
        </form>

        <p className="text-center text-xs opacity-50 mt-5">Default: admin / admin123</p>
      </div>
    </div>
  );
}
