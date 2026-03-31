package concurrent

import (
	"context"
	"sync"

	"golang.org/x/sync/errgroup"
)

// FanOut executes fn for each item in items with bounded concurrency.
// Results are collected thread-safely. Errors are collected, not propagated.
func FanOut[T any, R any](
	ctx context.Context,
	items []T,
	maxWorkers int,
	fn func(ctx context.Context, item T) (R, error),
) (successes []R, failures []error) {
	var mu sync.Mutex
	g, gCtx := errgroup.WithContext(ctx)
	g.SetLimit(maxWorkers)

	for i := range items {
		item := items[i]
		g.Go(func() error {
			result, err := fn(gCtx, item)
			mu.Lock()
			defer mu.Unlock()
			if err != nil {
				failures = append(failures, err)
			} else {
				successes = append(successes, result)
			}
			return nil
		})
	}
	g.Wait()
	return
}
