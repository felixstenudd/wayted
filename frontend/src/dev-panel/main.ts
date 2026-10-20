import '@fontsource-variable/schibsted-grotesk'
import { VueQueryPlugin, type VueQueryPluginOptions } from '@tanstack/vue-query'
import { createApp } from 'vue'

import './main.css'

import App from './App.vue'
import { i18n } from './i18n'

const vueQueryOptions: VueQueryPluginOptions = {
	queryClientConfig: {
		defaultOptions: {
			queries: {
				retry: false,
				refetchOnWindowFocus: false,
			},
		},
	},
}

createApp(App).use(i18n).use(VueQueryPlugin, vueQueryOptions).mount('#app')
