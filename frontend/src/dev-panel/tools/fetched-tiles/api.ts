import { useQuery } from '@tanstack/vue-query'

import { api } from '../../dev-api/client'
import { unwrap } from '../../dev-api/problem'

export function useFetchedTiles() {
	return useQuery({
		queryKey: ['tiles', 'fetched'],
		queryFn: () => unwrap(api.GET('/tiles/fetched')),
		// shallow: thousands of features must not become reactive proxies
		shallow: true,
	})
}
