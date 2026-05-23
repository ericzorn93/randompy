package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"sync"
	"sync/atomic"
	"time"

	"golang.org/x/sync/semaphore"
)

const (
	maxConcurrency = 100
	requestCount   = 1000
	requestURL     = "https://randompy.fly.dev/todos"
	timeout        = 5 * time.Minute
)

var (
	errorCount uint32 = 0
)

func makeCall(ctx context.Context, client *http.Client, i int) (int, error) {
	log.Printf("Making call %d", i)

	start := time.Now()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, requestURL, nil)
	if err != nil {
		return 0, err
	}

	resp, err := client.Do(req)
	if err != nil {
		return 0, err
	}
	defer resp.Body.Close()

	elapsed := time.Since(start).Seconds()
	log.Printf("Call %d completed in %.2f seconds", i, elapsed)
	return resp.StatusCode, nil
}

func main() {
	logger := log.New(os.Stdout, "", log.LstdFlags)
	log.SetOutput(logger.Writer())

	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	sem := semaphore.NewWeighted(int64(maxConcurrency))
	var wg sync.WaitGroup

	transport := &http.Transport{
		MaxIdleConns:          maxConcurrency,
		MaxIdleConnsPerHost:   maxConcurrency,
		MaxConnsPerHost:       maxConcurrency,
		IdleConnTimeout:       90 * time.Second,
		TLSHandshakeTimeout:   10 * time.Second,
		ExpectContinueTimeout: 1 * time.Second,
	}
	client := &http.Client{
		Transport: transport,
		Timeout:   timeout,
	}
	statuses := make([]int, requestCount)
	var statusMu sync.Mutex
	var errorOccurred bool

	start := time.Now()
	for i := 1; i <= requestCount; i++ {
		if err := sem.Acquire(ctx, 1); err != nil {
			log.Printf("Failed to acquire semaphore for call %d: %v", i, err)
			errorOccurred = true
			atomic.AddUint32(&errorCount, 1)
			break
		}

		wg.Go(func() {
			defer sem.Release(1)

			status, err := makeCall(ctx, client, i)
			if err != nil {
				log.Printf("Call %d failed: %v", i, err)
				statusMu.Lock()
				errorOccurred = true
				atomic.AddUint32(&errorCount, 1)
				statusMu.Unlock()
				return
			}

			statusMu.Lock()
			statuses[i-1] = status
			statusMu.Unlock()
		})
	}

	wg.Wait()
	totalTime := time.Since(start).Seconds()

	successCount := 0
	for _, status := range statuses {
		if status == http.StatusOK {
			successCount++
		}
	}

	log.Printf("All calls completed with success codes: %d in %.2f seconds", successCount, totalTime)
	if errorOccurred && errorCount > 0 {
		fmt.Fprintln(os.Stderr, "Some calls failed. Check logs for details.")
	}
}
