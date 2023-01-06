package main

import (
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/gorilla/mux"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

func recordMetrics() {
	go func() {
		for {
			opsProcessed.Inc()

			totalPluginApiDuration.WithLabelValues("pluginId123", "apiName_aaaa", "success_true").Observe(float64(time.Now().Minute()))

			time.Sleep(5 * time.Second)
		}
	}()
}

var (
	namespace = "myapp"

	opsProcessed = prometheus.NewCounter(prometheus.CounterOpts{
		Namespace: namespace,
		Subsystem: "processed",
		Name:      "ops_total",
		Help:      "The total number of processed events",
	})

	totalPluginApiDuration = prometheus.NewHistogramVec(prometheus.HistogramOpts{
		Namespace: namespace,
		Subsystem: "api",
		Name:      "plugin_time",
	}, []string{"pluginID", "apiName", "success"})
)

func init() {
	prometheus.MustRegister(
		opsProcessed,
		totalPluginApiDuration,
	)
}

func main() {
	recordMetrics()

	// http.Handle("/metrics", promhttp.Handler())
	// http.ListenAndServe(":2112", nil)

	router := mux.NewRouter()

	// Prometheus endpoint
	router.Path("/metrics").Handler(promhttp.Handler())

	// Serving static files
	router.PathPrefix("/").Handler(http.FileServer(http.Dir("./static/")))

	fmt.Println("Serving requests on port 2112")
	err := http.ListenAndServe(":2112", router)
	log.Fatal(err)
}
