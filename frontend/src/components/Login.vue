<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { api, user } from '../composables/useAuth'
const router = useRouter()
const register = ref(false), busy = ref(false), error = ref(''), message = ref('')
const form = reactive({ name: '', email: '', password: '', student_id: '', contact_details: '' })
async function submit() {
  error.value = ''; message.value = ''; busy.value = true
  try {
    if (register.value) {
      await api('/register', 'POST', form); register.value = false
      message.value = 'Registration complete. Log in to book your examination.'
    } else {
      user.value = (await api('/login', 'POST', form)).user
      await router.push('/' + user.value.role + '/dashboard')
    }
  } catch(e) { error.value = e.message } finally { busy.value = false }
}
</script>
<template>
  <div class="row justify-content-center py-4">
    <div class="col-lg-5 col-md-8">
      <div class="card border-0 shadow-sm p-4">
        <p class="text-primary text-uppercase small fw-semibold">Welcome to EMP</p>
        <h1 class="h3">{{ register ? 'Create your student account' : 'Sign in to your portal' }}</h1>
        <p class="text-secondary">{{ register ? 'Register to find examinations, book a slot and view results.' : 'Manage examinations, schedules and results in one place.' }}</p>
        <div v-if="error" role="alert" class="alert alert-danger">{{ error }}</div>
        <div v-if="message" role="status" class="alert alert-success">{{ message }}</div>
        <form @submit.prevent="submit">
          <template v-if="register">
            <label class="form-label" for="name">Full name</label><input id="name" v-model="form.name" class="form-control mb-3" required maxlength="100">
            <label class="form-label" for="sid">Student ID</label><input id="sid" v-model="form.student_id" class="form-control mb-3" required maxlength="50">
            <label class="form-label" for="contact">Contact details</label><input id="contact" v-model="form.contact_details" class="form-control mb-3" maxlength="200">
          </template>
          <label class="form-label" for="email">Email</label><input id="email" v-model="form.email" type="email" autocomplete="username" class="form-control mb-3" required maxlength="120">
          <label class="form-label" for="password">Password</label><input id="password" v-model="form.password" type="password" :autocomplete="register ? 'new-password' : 'current-password'" class="form-control mb-4" required :minlength="register ? 8 : 1" maxlength="128">
          <button class="btn btn-primary w-100" :disabled="busy">{{ busy ? 'Please wait…' : register ? 'Create account' : 'Sign in' }}</button>
        </form>
        <button class="btn btn-link mt-3" @click="register = !register; error = ''; message = ''">{{ register ? 'Already registered? Sign in' : 'New student? Create an account' }}</button>
        <p class="text-secondary small text-center mb-0">Examiner accounts are created by the administrator.</p>
      </div>
    </div>
  </div>
</template>
