<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, user } from '../composables/useAuth'
import RecordForm from './RecordForm.vue'
const route = useRoute(), router = useRouter()
const role = computed(() => user.value?.role), tab = computed(() => route.params.tab || 'dashboard')
const tabs = {
  admin: [['dashboard','Overview'],['courses','Courses'],['examinations','Examinations'],['examiners','Examiners'],['students','Students'],['slots','All slots'],['bookings','Bookings'],['reports','Reports']],
  examiner: [['dashboard','Overview'],['examinations','Assigned examinations'],['slots','My slots'],['bookings','Students & evaluations']],
  student: [['dashboard','Overview'],['examinations','Examinations'],['slots','Available slots'],['bookings','My bookings'],['history','History'],['results','Results'],['profile','Profile']]
}
const heading = computed(() => tabs[role.value]?.find(x => x[0] === tab.value)?.[1] || 'Overview')
const rows = ref([]), stats = ref({}), dashboard = ref({}), courses = ref([]), examiners = ref([]), exams = ref([]), allSlots = ref([])
const loading = ref(false), busy = ref(false), error = ref(''), notice = ref(''), query = ref(''), typeFilter = ref(''), courseFilter = ref(''), statusFilter = ref('')
const form = ref(null), formError = ref(''), rubricExam = ref(null), rubrics = ref([]), detail = ref(null), exports = ref([])
let poll
const prefix = computed(() => '/' + role.value)
const filtered = computed(() => rows.value.filter(r => {
  const text = JSON.stringify(r).toLowerCase()
  return (!query.value || text.includes(query.value.toLowerCase())) &&
    (!typeFilter.value || r.examination_type === typeFilter.value) &&
    (!courseFilter.value || String(r.course_id) === String(courseFilter.value)) &&
    (!statusFilter.value || r.status === statusFilter.value)
}))
const label = key => key.replaceAll('_',' ').replace(/\b\w/g, c => c.toUpperCase())
const stamp = value => value ? new Date(value).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }) : '—'
const localInput = value => {
  if (!value) return ''
  const parts = new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(value))
  return parts.replace(' ','T')
}
const option = (value,label) => ({ value,label })
const select = (key,label,options,extra={}) => ({key,label,type:'select',options,...extra})
const field = (key,label,type='text',extra={}) => ({key,label,type,...extra})
const peopleOptions = computed(() => examiners.value.filter(e => e.active).map(e => option(e.id,e.name)))
const courseOptions = computed(() => courses.value.map(c => option(c.id,c.course_code+' · '+c.course_name)))
const examOptions = computed(() => exams.value.filter(e => !e.archived).map(e => option(e.id,e.examination_name)))
const timeFields = ['slot_creation_start','slot_creation_end','slot_booking_start','slot_booking_end'].map(k => field(k,label(k)+' (IST)','datetime-local'))
const slotFields = () => [
  field('date','Date','date'),field('start_time','Start time (IST)','time'),field('end_time','End time (IST)','time'),
  field('max_student_capacity','Student capacity','number',{min:1}),field('meeting_link','Meeting link','url',{required:false,maxlength:500})
]
async function load() {
  if (!role.value) return
  loading.value = true; error.value = ''; detail.value = null
  try {
    if (tab.value === 'dashboard') {
      const d = await api(prefix.value + '/dashboard')
      dashboard.value = d; stats.value = d.stats || {
        available_examinations: d.available_examinations.length,
        available_slots: d.available_slots.length,
        upcoming_examinations: d.upcoming_examinations.length,
        published_results: d.published_results.length
      }
      rows.value = role.value === 'student' ? d.upcoming_examinations : role.value === 'examiner' ? d.pending_evaluations : []
    } else if (tab.value === 'reports') {
      dashboard.value = await api('/admin/reports')
      stats.value = Object.fromEntries(Object.entries(dashboard.value).filter(([k]) => k !== 'most_active_examiners'))
      rows.value = dashboard.value.most_active_examiners
    } else if (tab.value === 'profile') {
      const d = await api('/student/profile')
      openForm('Edit profile',[field('name','Name'),field('email','Email','email'),field('contact_details','Contact details','text',{required:false})],d,'/student/profile','PUT')
    } else {
      rows.value = await api(prefix.value + '/' + tab.value + (tab.value === 'slots' && role.value === 'student' && route.query.exam ? '?examination_id='+route.query.exam : ''))
    }
    if (role.value === 'admin') {
      const data = await Promise.all([api('/admin/courses'),api('/admin/examiners'),api('/admin/examinations'),api('/admin/slots')])
      ;[courses.value,examiners.value,exams.value,allSlots.value] = data
    } else if (role.value === 'examiner') exams.value = await api('/examiner/examinations')
    else if (role.value === 'student') {
      exams.value = await api('/student/examinations')
      courses.value = [...new Map(exams.value.map(e => [e.course_id,{ id:e.course_id,course_code:e.course_code,course_name:e.course_name }])).values()]
    }
    if (role.value === 'student' && tab.value === 'dashboard') await refreshExports()
  } catch(e) { error.value = e.message } finally { loading.value = false }
}
watch(() => route.fullPath, () => { form.value=null; rubricExam.value=null; query.value=''; typeFilter.value=''; statusFilter.value=''; courseFilter.value=''; load() }, {immediate:true})
function openForm(title, fields, initial, url, method='POST', transform=null) {
  formError.value=''; form.value={title,fields,initial,url,method,transform}
  window.scrollTo({top:0,behavior:'smooth'})
}
async function save(data) {
  busy.value=true; formError.value=''
  try {
    const config=form.value
    await api(config.url,config.method,config.transform ? config.transform(data) : data)
    form.value=null; notice.value='Saved successfully.'
    if (rubricExam.value) await loadRubrics(rubricExam.value)
    await load()
    if (tab.value==='profile') user.value=(await api('/me')).user
  } catch(e) { formError.value=e.message } finally { busy.value=false }
}
async function action(url, body={}, message='Updated successfully.', method='POST') {
  error.value=''; busy.value=true
  try { await api(url,method,body); notice.value=message; await load(); if(rubricExam.value) await loadRubrics(rubricExam.value) }
  catch(e) { error.value=e.message } finally { busy.value=false }
}
function editCourse(c={}) {
  openForm(c.id?'Edit course':'Create course',[
    field('course_code','Course code'),field('course_name','Course name'),field('description','Description','textarea',{required:false}),
    ...(c.id?[select('status','Status',['active','archived'].map(x=>option(x,label(x))))]:[])
  ],{course_code:'',course_name:'',description:'',status:'active',...c},'/admin/courses'+(c.id?'/'+c.id:''),c.id?'PUT':'POST')
}
function editPerson(p={}) {
  const kind=tab.value
  openForm(p.id?'Edit account':'Create '+(kind==='students'?'student':'examiner'),[
    field('name','Full name'),field('email','Email','email'),
    field('password',p.id?'New password (leave blank to keep)':'Password','password',{required:!p.id,minlength:8,maxlength:128}),
    field(kind==='students'?'student_id':'department',kind==='students'?'Student ID':'Department'),
    field('contact_details','Contact details','text',{required:false}),
    ...(p.id?[select('active','Account status',[option(true,'Active'),option(false,'Inactive')])]:[])
  ],{name:'',email:'',password:'',student_id:'',department:'',contact_details:'',active:true,...p},'/admin/'+kind+(p.id?'/'+p.id:''),p.id?'PUT':'POST')
}
function editExam(e={}) {
  const initial={course_id:'',examination_name:'',examination_type:'Viva',duration:30,maximum_marks:100,instructions:'',examiner_ids:[],...e}
  timeFields.forEach(f=>initial[f.key]=localInput(e[f.key]))
  openForm(e.id?'Edit examination':'Create examination',[
    select('course_id','Course',courseOptions.value),field('examination_name','Examination name'),
    select('examination_type','Type',['Viva','Practical','Project Demo','Assessment'].map(x=>option(x,x))),
    field('duration','Duration (minutes)','number',{min:1,max:1440}),field('maximum_marks','Maximum marks','number',{min:1,step:'0.01'}),
    ...timeFields,{key:'examiner_ids',label:'Assigned examiners',type:'multi',options:peopleOptions.value,required:false,help:'Hold Ctrl / Command to select multiple examiners.'},
    field('instructions','Examination instructions','textarea',{required:false})
  ],initial,'/admin/examinations'+(e.id?'/'+e.id:''),e.id?'PUT':'POST')
}
async function loadRubrics(e) {
  rubricExam.value=e
  try { rubrics.value=await api(prefix.value+'/examinations/'+e.id+'/rubrics') } catch(err){error.value=err.message}
}
function editRubric(r={}) {
  openForm(r.id?'Edit criterion':'Add rubric criterion',[
    field('criterion_name','Criterion name'),field('maximum_marks','Maximum raw marks','number',{min:0.01,step:'0.01'}),
    field('weightage','Weight (%)','number',{min:0.01,max:100,step:'0.01'}),field('description','Description','textarea',{required:false})
  ],{criterion_name:'',maximum_marks:10,weightage:100,description:'',...r},
  r.id?'/admin/rubrics/'+r.id:'/admin/examinations/'+rubricExam.value.id+'/rubrics',r.id?'PUT':'POST')
}
function editSlot(s={}) {
  openForm(s.id?'Edit slot':'Create slot',[
    ...(!s.id?[select('examination_id','Assigned examination',examOptions.value)]:[]),...slotFields()
  ],{examination_id:'',date:'',start_time:'',end_time:'',max_student_capacity:1,meeting_link:'',...s},
  '/examiner/slots'+(s.id?'/'+s.id:''),s.id?'PUT':'POST')
}
function moveBooking(b) {
  const choices=allSlots.value.filter(s=>s.examination_id===b.examination_id && s.id!==b.slot_id && s.available_seats>0 && s.status==='available')
  openForm('Reschedule booking #'+b.id,[
    select('new_slot_id','New slot',choices.map(s=>option(s.id,s.date+' '+s.start_time+' · '+s.examiner_name+' · '+s.available_seats+' seats'))),
    field('reason','Reason for exceptional rescheduling','textarea')
  ],{booking_id:b.id,new_slot_id:'',reason:''},'/admin/reschedule')
}
function reassign(s) {
  openForm('Change examiner for slot #'+s.id,[
    select('examiner_id','New examiner',peopleOptions.value.filter(e=>e.value!==s.examiner_id)),
    field('reason','Reason for reassignment','textarea')
  ],{slot_id:s.id,examiner_id:'',reason:''},'/admin/reassign-examiner')
}
function rescheduleSlot(s) {
  openForm('Reschedule slot #'+s.id,[...slotFields(),field('reason','Reason','textarea')],{...s,reason:''},'/admin/slots/'+s.id+'/reschedule')
}
async function evaluate(b) {
  try {
    const criteria=await api('/examiner/examinations/'+b.examination_id+'/rubrics')
    requireCriteria(criteria)
    openForm('Evaluate '+b.student_name+' · '+b.examination_name,[
      ...criteria.map(r=>field('score_'+r.id,r.criterion_name+' / '+r.maximum_marks+' ('+r.weightage+'%)','number',{min:0,max:r.maximum_marks,step:'0.01',help:r.description})),
      field('remarks','Remarks / feedback','textarea',{required:false})
    ],Object.fromEntries([...criteria.map(r=>['score_'+r.id,'']),['remarks','']]),'/examiner/evaluate/'+b.id,'POST',
    d=>({remarks:d.remarks,scores:criteria.map(r=>({rubric_id:r.id,marks:Number(d['score_'+r.id])}))}))
  } catch(e) {error.value=e.message}
}
function requireCriteria(criteria) { if(!criteria.length) throw new Error('No rubric has been configured.') }
function confirmDelete(url, message) {
  if(window.confirm(message)) action(url,{},'Record removed.','DELETE')
}
async function startExport() {
  busy.value=true; error.value=''
  try {
    const job = await api('/student/exports','POST',{})
    exports.value = [{ id: job.id, status: 'queued', created_at: new Date().toISOString() }, ...exports.value]
    notice.value='Export queued. You will see a completion alert here.'
    await refreshExports()
  } catch(e){error.value=e.message} finally {busy.value=false}
}
async function refreshExports() {
  const previous=exports.value
  exports.value=await api('/student/exports')
  if(exports.value.some(j=>j.status==='completed' && previous.some(p=>p.id===j.id && p.status!=='completed')))
    notice.value='Your examination history export is ready to download.'
  clearTimeout(poll)
  if(exports.value.some(j=>['queued','running'].includes(j.status)))
    poll=setTimeout(()=>refreshExports().catch(e=>{error.value=e.message}),2000)
}
onUnmounted(()=>clearTimeout(poll))
const bookingTable=computed(()=>['bookings','history','results'].includes(tab.value) || (tab.value==='dashboard' && role.value!=='admin'))
const badge=status=>['completed','active','available','booking_open'].includes(status)?'text-bg-success':['cancelled','archived','closed'].includes(status)?'text-bg-secondary':'text-bg-primary'
</script>

<template>
  <nav class="nav nav-pills gap-1 mb-4 flex-wrap" aria-label="Portal sections">
    <router-link v-for="[key,title] in tabs[role]" :key="key" :to="'/'+role+'/'+key" class="nav-link" :class="{active:tab===key}">{{ title }}</router-link>
  </nav>
  <div class="d-flex flex-wrap align-items-start justify-content-between gap-2 mb-4">
    <div><p class="text-uppercase text-secondary small mb-1">{{ role }} workspace</p><h1 class="h2 mb-0">{{ heading }}</h1></div>
    <div class="d-flex gap-2">
      <button class="btn btn-outline-secondary" @click="load" :disabled="loading">Refresh</button>
      <button v-if="role==='admin' && tab==='courses'" class="btn btn-primary" @click="editCourse()">Create course</button>
      <button v-if="role==='admin' && tab==='examinations'" class="btn btn-primary" @click="editExam()">Create examination</button>
      <button v-if="role==='admin' && ['students','examiners'].includes(tab)" class="btn btn-primary" @click="editPerson()">Create account</button>
      <button v-if="role==='examiner' && tab==='slots'" class="btn btn-primary" @click="editSlot()">Create slot</button>
      <button v-if="role==='student' && tab==='dashboard'" class="btn btn-primary" @click="startExport" :disabled="busy">Export history as CSV</button>
    </div>
  </div>
  <div v-if="error" class="alert alert-danger" role="alert">{{ error }}</div>
  <div v-if="notice" class="alert alert-success alert-dismissible" role="status">{{ notice }}<button class="btn-close" aria-label="Dismiss" @click="notice=''"></button></div>
  <RecordForm v-if="form" :title="form.title" :fields="form.fields" :initial="form.initial" :busy="busy" :error="formError" @save="save" @cancel="form=null" />

  <div v-if="['dashboard','reports'].includes(tab)" class="row g-3 mb-4">
    <div v-for="(value,key) in stats" :key="key" class="col-6 col-xl-3">
      <div class="card h-100 border-0 shadow-sm"><div class="card-body"><p class="small text-secondary mb-2">{{ label(key) }}</p><p class="h2 mb-0">{{ value }}</p></div></div>
    </div>
  </div>
  <section v-if="role==='student' && tab==='dashboard'" class="mb-4">
    <div class="d-flex gap-2 mb-3"><router-link class="btn btn-outline-primary" to="/student/slots">Find an available slot</router-link><router-link class="btn btn-outline-primary" to="/student/results">View published results</router-link></div>
    <div v-if="exports.length" class="card mb-4"><div class="card-body">
      <h2 class="h5">History exports</h2>
      <div v-for="job in exports" :key="job.id" class="d-flex flex-wrap gap-3 align-items-center py-2 border-bottom">
        <span>{{ stamp(job.created_at) }}</span><span class="badge" :class="badge(job.status)">{{ job.status }}</span>
        <a v-if="job.status==='completed'" :href="'/api/student/exports/'+job.id+'/download'" class="btn btn-sm btn-outline-success">Download CSV</a>
        <span v-if="job.error" class="text-danger">{{ job.error }}</span>
      </div>
    </div></div>
    <h2 class="h5">Upcoming examinations</h2>
  </section>
  <p v-if="role==='examiner' && tab==='dashboard'" class="text-secondary">Bookings awaiting evaluation or completion are listed below.</p>
  <div v-if="role==='admin' && tab==='dashboard'" class="card border-0 shadow-sm"><div class="card-body">
    <h2 class="h5">Examination workflow</h2>
    <ol class="mb-0"><li>Create a course and examination with its timelines.</li><li>Assign examiners and add rubric criteria totaling 100%.</li><li>Open slot creation, then open student booking during its configured period.</li><li>Review completed evaluations and publish results from Examinations.</li></ol>
  </div></div>

  <section v-if="rubricExam" class="card mb-4 border-primary"><div class="card-body">
    <div class="d-flex justify-content-between gap-2"><h2 class="h5">Rubric · {{ rubricExam.examination_name }}</h2><button class="btn-close" aria-label="Close rubric" @click="rubricExam=null"></button></div>
    <p class="text-secondary">Total weight: {{ rubrics.reduce((sum,r)=>sum+r.weightage,0) }}%. Final score = sum(raw score / criterion maximum × weight / 100 × examination maximum).</p>
    <button v-if="role==='admin'" class="btn btn-sm btn-primary mb-3" @click="editRubric()">Add criterion</button>
    <div class="table-responsive"><table class="table"><thead><tr><th>Criterion</th><th>Maximum</th><th>Weight</th><th>Description</th><th v-if="role==='admin'">Actions</th></tr></thead>
      <tbody><tr v-for="r in rubrics" :key="r.id"><td>{{ r.criterion_name }}</td><td>{{ r.maximum_marks }}</td><td>{{ r.weightage }}%</td><td>{{ r.description }}</td><td v-if="role==='admin'"><button class="btn btn-sm btn-outline-primary me-2" @click="editRubric(r)">Edit</button><button class="btn btn-sm btn-outline-danger" @click="confirmDelete('/admin/rubrics/'+r.id,'Delete this criterion?')">Delete</button></td></tr></tbody>
    </table></div>
  </div></section>

  <div v-if="!['dashboard','reports','profile'].includes(tab)" class="row g-2 mb-3">
    <div class="col-md"><label class="visually-hidden" for="search">Search records</label><input id="search" v-model="query" class="form-control" placeholder="Search by name, course, ID or status…"></div>
    <template v-if="tab==='examinations'">
      <div class="col-md-2"><select v-model="typeFilter" aria-label="Examination type" class="form-select"><option value="">All types</option><option>Viva</option><option>Practical</option><option>Project Demo</option><option>Assessment</option></select></div>
      <div class="col-md-2"><select v-model="courseFilter" aria-label="Course filter" class="form-select"><option value="">All courses</option><option v-for="c in courses" :key="c.id" :value="c.id">{{ c.course_name }}</option></select></div>
      <div class="col-md-2"><select v-model="statusFilter" aria-label="Status filter" class="form-select"><option value="">All statuses</option><option v-for="s in ['draft','slot_creation','booking_open','closed','completed']" :key="s">{{ s }}</option></select></div>
    </template>
  </div>
  <p v-if="loading" role="status" class="text-secondary">Loading records…</p>

  <div v-if="tab==='examinations'" class="row g-3 mb-4">
    <div v-for="e in filtered" :key="e.id" class="col-xl-6">
      <article class="card h-100 border-0 shadow-sm"><div class="card-body">
        <div class="d-flex justify-content-between gap-2"><h2 class="h5">{{ e.examination_name }}</h2><span class="badge align-self-start" :class="badge(e.status)">{{ e.archived?'archived':label(e.status) }}</span></div>
        <p class="text-secondary">{{ e.course_name }} · {{ e.examination_type }} · {{ e.duration }} min · {{ e.maximum_marks }} marks</p>
        <dl class="row small mb-2"><dt class="col-sm-3">Slot creation</dt><dd class="col-sm-9">{{ stamp(e.slot_creation_start) }} – {{ stamp(e.slot_creation_end) }}</dd><dt class="col-sm-3">Student booking</dt><dd class="col-sm-9">{{ stamp(e.slot_booking_start) }} – {{ stamp(e.slot_booking_end) }}</dd></dl>
        <p class="small" style="white-space:pre-wrap">{{ e.instructions || 'No additional instructions.' }}</p>
        <div class="d-flex flex-wrap gap-2">
          <template v-if="role==='admin'">
            <button class="btn btn-sm btn-outline-primary" @click="editExam(e)" :disabled="e.archived || e.status==='completed'">Edit</button>
            <button class="btn btn-sm btn-outline-primary" @click="loadRubrics(e)">Rubrics</button>
            <button class="btn btn-sm btn-outline-secondary" @click="action('/admin/examinations/'+e.id+'/status',{status:'slot_creation'})" :disabled="busy || e.archived || e.booking_started">Open slot creation</button>
            <button class="btn btn-sm btn-outline-secondary" @click="action('/admin/examinations/'+e.id+'/status',{status:'closed'})" :disabled="busy || e.archived">Close period</button>
            <button class="btn btn-sm btn-outline-secondary" @click="action('/admin/examinations/'+e.id+'/status',{status:'booking_open'})" :disabled="busy || e.archived">Open booking</button>
            <button class="btn btn-sm btn-outline-success" @click="action('/admin/examinations/'+e.id+'/status',{status:'completed'})" :disabled="busy || e.archived">Complete exam</button>
            <button class="btn btn-sm btn-success" @click="action('/admin/examinations/'+e.id+'/publish',{},'Completed results published.')" :disabled="busy">Publish results</button>
            <button class="btn btn-sm btn-outline-secondary" @click="action('/admin/examinations/'+e.id+'/status',{status:'archived'})" :disabled="busy || e.archived">Archive</button>
            <button class="btn btn-sm btn-outline-danger" @click="confirmDelete('/admin/examinations/'+e.id,'Remove this examination? Only examinations without slots can be removed.')">Delete</button>
          </template>
          <button v-if="role==='examiner'" class="btn btn-sm btn-outline-primary" @click="loadRubrics(e)">View rubric</button>
          <router-link v-if="role==='student'" class="btn btn-primary" :to="'/student/slots?exam='+e.id">View available slots</router-link>
        </div>
      </div></article>
    </div>
  </div>

  <div v-if="tab==='courses'" class="table-responsive card border-0 shadow-sm">
    <table class="table table-hover align-middle mb-0"><thead class="table-light"><tr><th>Code</th><th>Course</th><th>Description</th><th>Status</th><th>Actions</th></tr></thead><tbody>
      <tr v-for="c in filtered" :key="c.id"><td>{{ c.course_code }}</td><td>{{ c.course_name }}</td><td>{{ c.description }}</td><td>{{ c.status }}</td><td class="text-nowrap"><button class="btn btn-sm btn-outline-primary me-2" @click="editCourse(c)">Edit</button><button class="btn btn-sm btn-outline-danger" @click="confirmDelete('/admin/courses/'+c.id,'Remove course? Courses with examinations must be archived instead.')">Delete</button></td></tr>
    </tbody></table>
  </div>
  <div v-if="['students','examiners'].includes(tab)" class="table-responsive card border-0 shadow-sm">
    <table class="table table-hover align-middle mb-0"><thead class="table-light"><tr><th>Name</th><th>Email</th><th>{{ tab==='students'?'Student ID':'Department' }}</th><th>Contact</th><th>Status</th><th>Actions</th></tr></thead><tbody>
      <tr v-for="p in filtered" :key="p.id"><td>{{ p.name }}</td><td>{{ p.email }}</td><td>{{ p.student_id || p.department }}</td><td>{{ p.contact_details }}</td><td>{{ p.active?'Active':'Inactive' }}</td><td class="text-nowrap"><button class="btn btn-sm btn-outline-primary me-2" @click="editPerson(p)">Edit</button><button class="btn btn-sm btn-outline-danger" @click="confirmDelete('/admin/'+tab+'/'+p.id,'Deactivate account? Historical records will be retained.')">Deactivate</button></td></tr>
    </tbody></table>
  </div>
  <div v-if="tab==='slots'" class="table-responsive card border-0 shadow-sm">
    <table class="table table-hover align-middle mb-0"><thead class="table-light"><tr><th>Slot / Examination</th><th>Examiner</th><th>Date / time (IST)</th><th>Seats</th><th>Status</th><th>Actions</th></tr></thead><tbody>
      <tr v-for="s in filtered" :key="s.id"><td>#{{ s.id }} · {{ s.examination_name }}<small class="d-block text-secondary">{{ s.course_name }}</small></td><td>{{ s.examiner_name }}</td><td>{{ s.date }}<br>{{ s.start_time }} – {{ s.end_time }}<a v-if="s.meeting_link" :href="s.meeting_link" target="_blank" rel="noopener" class="d-block">Meeting link</a></td><td>{{ s.available_seats }} / {{ s.max_student_capacity }}</td><td><span class="badge" :class="badge(s.status)">{{ s.status }}</span></td><td>
        <div class="d-flex flex-wrap gap-2">
          <button v-if="role==='student'" class="btn btn-sm btn-primary" @click="action('/student/bookings',{slot_id:s.id},'Slot booked successfully.')" :disabled="busy">Book slot</button>
          <template v-if="role==='examiner'"><button class="btn btn-sm btn-outline-primary" @click="editSlot(s)">Edit</button><button class="btn btn-sm btn-outline-danger" @click="confirmDelete('/examiner/slots/'+s.id,'Remove this unbooked slot?')">Delete</button><router-link class="btn btn-sm btn-outline-secondary" to="/examiner/bookings">View students</router-link></template>
          <template v-if="role==='admin'"><button class="btn btn-sm btn-outline-primary" @click="rescheduleSlot(s)">Reschedule</button><button class="btn btn-sm btn-outline-secondary" @click="reassign(s)">Change examiner</button></template>
        </div>
      </td></tr>
    </tbody></table>
  </div>
  <div v-if="bookingTable" class="table-responsive card border-0 shadow-sm">
    <table class="table table-hover align-middle mb-0"><thead class="table-light"><tr><th>Booking / examination</th><th v-if="role!=='student'">Student</th><th>Schedule (IST)</th><th>Examiner</th><th>Status</th><th>Marks</th><th>Actions</th></tr></thead><tbody>
      <tr v-for="b in filtered" :key="b.id">
        <td>#{{ b.id }} · {{ b.examination_name }}<small class="d-block text-secondary">{{ b.course_name }}</small></td>
        <td v-if="role!=='student'">{{ b.student_name }}<small class="d-block">{{ b.student_code }}</small></td>
        <td>{{ b.date }}<br>{{ b.start_time }} – {{ b.end_time }}</td><td>{{ b.examiner_name }}</td>
        <td><span class="badge" :class="badge(b.status)">{{ b.status }}</span><small class="d-block text-secondary">Exam: {{ label(b.examination_status) }}</small></td>
        <td>{{ b.evaluation ? b.evaluation.total_marks+' / '+b.maximum_marks : '—' }}<small v-if="b.evaluation" class="d-block">{{ b.evaluation.published_at?'Published':'Unpublished' }}</small></td>
        <td><div class="d-flex flex-wrap gap-2">
          <button class="btn btn-sm btn-outline-secondary" @click="detail=b">Details</button>
          <button v-if="role==='student' && b.status==='booked'" class="btn btn-sm btn-outline-danger" @click="action('/student/bookings/'+b.id+'/cancel',{},'Booking cancelled.')" :disabled="busy">Cancel</button>
          <button v-if="role==='admin' && b.status==='booked' && !b.evaluation" class="btn btn-sm btn-outline-primary" @click="moveBooking(b)">Reschedule</button>
          <button v-if="role==='examiner' && b.status==='booked' && !b.evaluation" class="btn btn-sm btn-primary" @click="evaluate(b)">Evaluate</button>
          <button v-if="role==='examiner' && b.status==='booked' && b.evaluation" class="btn btn-sm btn-success" @click="action('/examiner/complete-examination',{booking_id:b.id},'Completed. Results await Admin publication.')" :disabled="busy">Mark completed</button>
        </div></td>
      </tr>
    </tbody></table>
  </div>
  <section v-if="detail" class="card mt-4 border-primary"><div class="card-body">
    <div class="d-flex justify-content-between"><h2 class="h5">Booking #{{ detail.id }} · {{ detail.examination_name }}</h2><button class="btn-close" aria-label="Close details" @click="detail=null"></button></div>
    <p style="white-space:pre-wrap">{{ detail.instructions || 'No additional instructions.' }}</p>
    <a v-if="detail.meeting_link" :href="detail.meeting_link" target="_blank" rel="noopener">Join examination meeting</a>
    <template v-if="detail.evaluation"><h3 class="h6 mt-3">Evaluation feedback</h3><p style="white-space:pre-wrap">{{ detail.evaluation.remarks || 'No remarks.' }}</p>
      <ul><li v-for="s in detail.evaluation.scores" :key="s.rubric_id">{{ s.criterion_name }}: {{ s.marks }} / {{ s.maximum_marks }} · {{ s.weightage }}% weight</li></ul>
    </template>
    <h3 class="h6 mt-3">Booking history</h3><ul><li v-for="(event,i) in detail.events" :key="i">{{ stamp(event.created_at) }} · {{ label(event.action) }}<span v-if="event.details.reason"> · {{ event.details.reason }}</span></li></ul>
  </div></section>
  <div v-if="tab==='reports'" class="card"><div class="card-body"><h2 class="h5">Most active examiners</h2><p v-for="r in rows" :key="r.examiner_id">{{ r.name }} · {{ r.completed_bookings }} completed bookings</p><p v-if="!rows.length" class="text-secondary">No completed examinations yet.</p><p class="text-secondary small mb-0">These are all-time statistics. The scheduled email contains the previous calendar month's statistics.</p></div></div>
  <p v-if="!loading && !filtered.length && !['profile','reports'].includes(tab) && !(tab==='dashboard' && role==='admin')" class="text-secondary py-4 text-center">No records to display.</p>
</template>
