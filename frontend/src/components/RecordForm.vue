<script setup>
import { reactive, watch } from 'vue'
const props = defineProps({ title: String, fields: Array, initial: Object, busy: Boolean, error: String })
const emit = defineEmits(['save', 'cancel'])
const form = reactive({})
watch(() => props.initial, value => {
  Object.keys(form).forEach(k => delete form[k])
  Object.assign(form, value || {})
}, { immediate: true })
</script>
<template>
  <section class="card border-primary shadow-sm mb-4" aria-label="Edit form">
    <div class="card-body">
      <h2 class="h5 mb-3">{{ title }}</h2>
      <div v-if="error" class="alert alert-danger" role="alert">{{ error }}</div>
      <form @submit.prevent="emit('save', { ...form })">
        <div class="row g-3">
          <div v-for="field in fields" :key="field.key" :class="field.type === 'textarea' ? 'col-12' : 'col-md-6'">
            <label class="form-label" :for="'field-' + field.key">{{ field.label }}</label>
            <textarea v-if="field.type === 'textarea'" :id="'field-' + field.key" v-model="form[field.key]" class="form-control" rows="3" :required="field.required !== false" :maxlength="field.maxlength || 5000"></textarea>
            <select v-else-if="field.type === 'select' || field.type === 'multi'" :id="'field-' + field.key" v-model="form[field.key]" class="form-select" :multiple="field.type === 'multi'" :required="field.required !== false">
              <option v-if="field.type !== 'multi'" disabled value="">Choose an option</option>
              <option v-for="option in field.options" :key="String(option.value)" :value="option.value">{{ option.label }}</option>
            </select>
            <input v-else :id="'field-' + field.key" v-model="form[field.key]" :type="field.type || 'text'" class="form-control" :required="field.required !== false" :min="field.min" :max="field.max" :step="field.step || (field.type === 'number' ? '1' : undefined)" :minlength="field.minlength" :maxlength="field.maxlength || 200">
            <div v-if="field.help" class="form-text">{{ field.help }}</div>
          </div>
        </div>
        <div class="d-flex gap-2 mt-4">
          <button class="btn btn-primary" :disabled="busy">{{ busy ? 'Saving…' : 'Save' }}</button>
          <button type="button" class="btn btn-outline-secondary" :disabled="busy" @click="emit('cancel')">Cancel</button>
        </div>
      </form>
    </div>
  </section>
</template>
