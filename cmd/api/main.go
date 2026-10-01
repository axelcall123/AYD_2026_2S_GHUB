package main

import (
	"log"
	"net/http"
	"os"
	"time"

	"ayd/tareas-api/internal/tareas"
)

func main() {
	addr := ":8080"
	if p := os.Getenv("PORT"); p != "" {
		addr = ":" + p
	}

	srv := &http.Server{
		Addr:              addr,
		Handler:           tareas.NewHandler(tareas.NewStore()),
		ReadHeaderTimeout: 5 * time.Second,
	}

	log.Printf("API escuchando en %s", addr)
	log.Fatal(srv.ListenAndServe())
}
