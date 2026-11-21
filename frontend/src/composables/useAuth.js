import { ref } from 'vue'
export const user = ref(null)
export async function api(path, method = 'GET', body) {
  const csrf = document.cookie.split('; ').find(c => c.startsWith('csrf_access_token='))?.split('=')[1]
  const response = await fetch('/api' + path, {
    method, credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...(csrf ? { 'X-CSRF-TOKEN': decodeURIComponent(csrf) } : {}) },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {})
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.error || data.msg || 'Request failed. Please try again.')
  return data
}
export async function restore() {
  try { user.value = (await api('/me')).user } catch { user.value = null }
}
