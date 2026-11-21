<script setup>
import { useRouter } from 'vue-router'
import { user, api } from './composables/useAuth'
const router = useRouter()
async function logout() {
  try { await api('/logout', 'POST', {}) } finally { user.value = null; router.push('/login') }
}
</script>
<template>
  <div class="min-vh-100 bg-light">
    <header class="navbar navbar-dark bg-dark py-3">
      <div class="container-fluid px-lg-5">
        <router-link class="navbar-brand fw-semibold" :to="user ? '/' + user.role + '/dashboard' : '/login'">Examination Management Portal</router-link>
        <div v-if="user" class="d-flex align-items-center gap-3 text-white">
          <span class="small">{{ user.name }} <span class="badge text-bg-secondary ms-1">{{ user.role }}</span></span>
          <button class="btn btn-sm btn-outline-light" @click="logout">Log out</button>
        </div>
      </div>
    </header>
    <main class="container-fluid px-lg-5 py-4"><router-view /></main>
    <footer class="container-fluid px-lg-5 py-4 border-top text-secondary small">Examination Management Portal V2 · All slot times are Asia/Kolkata (IST).</footer>
  </div>
</template>
