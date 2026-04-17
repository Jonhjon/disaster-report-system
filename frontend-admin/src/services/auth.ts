const BASE_URL = "/api";

export async function login(username: string, password: string): Promise<string> {
  const form = new URLSearchParams();
  form.set("username", username);
  form.set("password", password);

  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form,
  });

  if (!res.ok) {
    if (res.status === 401) throw new Error("帳號或密碼錯誤");
    throw new Error("登入失敗");
  }

  const data = await res.json();
  localStorage.setItem("token", data.access_token);
  return data.access_token;
}

export function logout(): void {
  localStorage.removeItem("token");
}

export function getStoredToken(): string | null {
  return localStorage.getItem("token");
}
