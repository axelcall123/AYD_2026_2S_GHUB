package tareas

import (
	"encoding/json"
	"errors"
	"net/http"
)

type handler struct {
	store *Store
}

func NewHandler(s *Store) http.Handler {
	h := &handler{store: s}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /salud", h.salud)
	mux.HandleFunc("GET /tareas", h.listar)
	mux.HandleFunc("POST /tareas", h.crear)
	return mux
}

func (h *handler) salud(w http.ResponseWriter, _ *http.Request) {
	escribirJSON(w, http.StatusOK, map[string]string{"estado": "ok"})
}

func (h *handler) listar(w http.ResponseWriter, _ *http.Request) {
	escribirJSON(w, http.StatusOK, h.store.Listar())
}

func (h *handler) crear(w http.ResponseWriter, r *http.Request) {
	r.Body = http.MaxBytesReader(w, r.Body, 1<<20)

	var entrada struct {
		Titulo string `json:"titulo"`
	}
	if err := json.NewDecoder(r.Body).Decode(&entrada); err != nil {
		escribirJSON(w, http.StatusBadRequest, map[string]string{"error": "JSON inválido"})
		return
	}

	t, err := h.store.Crear(entrada.Titulo)
	if errors.Is(err, ErrTituloVacio) {
		escribirJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	if err != nil {
		escribirJSON(w, http.StatusInternalServerError, map[string]string{"error": "error interno"})
		return
	}

	escribirJSON(w, http.StatusCreated, t)
}

func escribirJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}
