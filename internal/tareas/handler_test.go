package tareas

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestSalud(t *testing.T) {
	srv := NewHandler(NewStore())
	req := httptest.NewRequest(http.MethodGet, "/salud", nil)
	rec := httptest.NewRecorder()

	srv.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, esperado 200", rec.Code)
	}
}

func TestCrearYListar(t *testing.T) {
	srv := NewHandler(NewStore())

	body := strings.NewReader(`{"titulo":"Preparar conferencia"}`)
	req := httptest.NewRequest(http.MethodPost, "/tareas", body)
	rec := httptest.NewRecorder()
	srv.ServeHTTP(rec, req)

	if rec.Code != http.StatusCreated {
		t.Fatalf("POST status = %d, esperado 201", rec.Code)
	}

	req = httptest.NewRequest(http.MethodGet, "/tareas", nil)
	rec = httptest.NewRecorder()
	srv.ServeHTTP(rec, req)

	var lista []Tarea
	if err := json.NewDecoder(rec.Body).Decode(&lista); err != nil {
		t.Fatalf("respuesta inválida: %v", err)
	}
	if len(lista) != 1 || lista[0].Titulo != "Preparar conferencia" {
		t.Fatalf("lista = %+v", lista)
	}
}

func TestCrearTituloVacio(t *testing.T) {
	srv := NewHandler(NewStore())
	req := httptest.NewRequest(http.MethodPost, "/tareas", strings.NewReader(`{"titulo":""}`))
	rec := httptest.NewRecorder()

	srv.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, esperado 400", rec.Code)
	}
}

func TestCrearJSONInvalido(t *testing.T) {
	srv := NewHandler(NewStore())
	req := httptest.NewRequest(http.MethodPost, "/tareas", strings.NewReader(`no es json`))
	rec := httptest.NewRecorder()

	srv.ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, esperado 400", rec.Code)
	}
}
