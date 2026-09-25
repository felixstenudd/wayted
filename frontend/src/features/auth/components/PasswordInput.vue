<script setup lang="ts">
import { Eye, EyeOff } from '@lucide/vue'
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { Input } from '@/shared/ui/input'

// Attributes (id, autocomplete, aria-*) belong on the input, not the wrapper.
defineOptions({ inheritAttrs: false })

const model = defineModel<string>({ required: true })

const { t } = useI18n()
const passwordVisible = ref(false)
</script>

<template>
	<div class="relative">
		<Input
			v-model="model"
			v-bind="$attrs"
			:type="passwordVisible ? 'text' : 'password'"
			class="pr-11"
		/>
		<button
			type="button"
			class="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-sm text-graphite transition-[color] duration-150 ease-out hover:text-ink"
			:aria-label="passwordVisible ? t('auth.password.hide') : t('auth.password.show')"
			@click="passwordVisible = !passwordVisible"
		>
			<EyeOff v-if="passwordVisible" class="size-4" aria-hidden="true" />
			<Eye v-else class="size-4" aria-hidden="true" />
		</button>
	</div>
</template>
