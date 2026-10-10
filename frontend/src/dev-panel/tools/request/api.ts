import { useMutation, useQueryClient } from '@tanstack/vue-query'

import { api } from '../../dev-api/client'
import { unwrap } from '../../dev-api/problem'
import type { AreaRequest } from '../../dev-api/types'
import { queuedTilesKey } from '../queue/api'

export function useRequestArea() {
	const queryClient = useQueryClient()
	return useMutation({
		mutationFn: (body: AreaRequest) => unwrap(api.POST('/requests', { body })),
		onSuccess: () => queryClient.invalidateQueries({ queryKey: queuedTilesKey }),
	})
}
