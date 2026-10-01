package tareas

import (
	"errors"
	"strings"
	"sync"
)

type Tarea struct {
	ID     int    `json:"id"`
	Titulo string `json:"titulo"`
	Hecha  bool   `json:"hecha"`
}

var ErrTituloVacio = errors.New("el título no puede estar vacío")

// Store guarda las tareas en memoria; es seguro para uso concurrente.
type Store struct {
	mu    sync.Mutex
	sig   int
	items []Tarea
}

func NewStore() *Store {
	return &Store{sig: 1}
}

func (s *Store) Crear(titulo string) (Tarea, error) {
	titulo = strings.TrimSpace(titulo)
	if titulo == "" {
		return Tarea{}, ErrTituloVacio
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	t := Tarea{ID: s.sig, Titulo: titulo}
	s.sig++
	s.items = append(s.items, t)
	return t, nil
}

func (s *Store) Listar() []Tarea {
	s.mu.Lock()
	defer s.mu.Unlock()

	copia := make([]Tarea, len(s.items))
	copy(copia, s.items)
	return copia
}
