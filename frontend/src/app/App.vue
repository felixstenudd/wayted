<script setup lang="ts">
import { useQueryClient } from '@tanstack/vue-query'
import { watch } from 'vue'
import { RouterView } from 'vue-router'

import { useAuthStore } from '@/features/auth'
import { usePlannerStore } from '@/features/route-planner'

const auth = useAuthStore()
const planner = usePlannerStore()
const queryClient = useQueryClient()

// Cached answers and the planner's weights belong to whoever was signed in. When they sign out
// or someone else signs in, nothing of theirs may show for the next person.
watch(
	() => auth.user?.email ?? null,
	(email, previousEmail) => {
		if (previousEmail === null || email === previousEmail) return
		queryClient.clear()
		planner.forgetDefaults()
	},
)
</script>

<template>
	<RouterView />
</template>
