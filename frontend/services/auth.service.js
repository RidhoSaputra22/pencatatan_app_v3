import { post } from "./api";

/**
 * Login with username + password. Returns { access_token }.
 */
export async function login(username, password) {
  return post("/api/auth/login", { username, password });
}
