import { createRouter, createWebHistory } from 'vue-router'
import Login from '../components/Login.vue'
import Portal from '../components/Portal.vue'
import { user, restore } from '../composables/useAuth'
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: Login },
    { path: '/:role(admin|examiner|student)/:tab?', component: Portal },
    { path: '/:pathMatch(.*)*', redirect: '/login' }
  ]
})
router.beforeEach(async to => {
  if (!user.value) await restore()
  if (!user.value && to.path !== '/login') return '/login'
  if (user.value && (to.path === '/login' || to.params.role !== user.value.role))
    return '/' + user.value.role + '/dashboard'
})
export default router
