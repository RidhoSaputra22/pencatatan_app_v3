import { get, post, put, del } from "./api";

/**
 * GET /api/users — list all users (admin only).
 */
export function fetchUsers() {
  return get("/api/users");
}

/**
 * POST /api/users — create a new user (admin only).
 */
export function createUser(data) {
  return post("/api/users", data);
}

/**
 * PUT /api/users/:id — update user (admin only).
 */
export function updateUser(userId, data) {
  return put(`/api/users/${userId}`, data);
}

/**
 * DELETE /api/users/:id — deactivate user (admin only).
 */
export function deleteUser(userId) {
  return del(`/api/users/${userId}`);
}
