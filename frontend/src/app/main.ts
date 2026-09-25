import '@fontsource-variable/schibsted-grotesk'
import { createApp } from 'vue'

import '@/assets/main.css'

import App from './App.vue'
import { i18n } from './plugins/i18n'
import { pinia } from './plugins/pinia'
import { VueQueryPlugin, vueQueryOptions } from './plugins/vue-query'
import { router } from './router'

createApp(App).use(pinia).use(router).use(i18n).use(VueQueryPlugin, vueQueryOptions).mount('#app')
