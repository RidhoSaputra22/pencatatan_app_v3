import { del, get, post, put } from "./api";

export function fetchEmployees() {
  return get("/api/employees");
}

export function createEmployee(formData) {
  return post("/api/employees", formData);
}

export function updateEmployee(employeeId, formData) {
  return put(`/api/employees/${employeeId}`, formData);
}

export function deleteEmployee(employeeId) {
  return del(`/api/employees/${employeeId}`);
}
