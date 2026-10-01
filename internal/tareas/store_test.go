package tareas

import (
	"errors"
	"sync"
	"testing"
)

func TestCrear(t *testing.T) {
	casos := []struct {
		nombre  string
		titulo  string
		wantErr error
	}{
		{"titulo valido", "Estudiar CI/CD", nil},
		{"titulo con espacios", "  Hacer demo  ", nil},
		{"titulo vacio", "", ErrTituloVacio},
		{"solo espacios", "   ", ErrTituloVacio},
	}

	for _, c := range casos {
		t.Run(c.nombre, func(t *testing.T) {
			s := NewStore()
			_, err := s.Crear(c.titulo)
			if !errors.Is(err, c.wantErr) {
				t.Fatalf("error = %v, esperado %v", err, c.wantErr)
			}
		})
	}
}

func TestCrearAsignaIDsSecuenciales(t *testing.T) {
	s := NewStore()
	a, _ := s.Crear("a")
	b, _ := s.Crear("b")
	if a.ID != 1 || b.ID != 2 {
		t.Fatalf("IDs = %d, %d; esperado 1, 2", a.ID, b.ID)
	}
}

func TestConcurrencia(t *testing.T) {
	s := NewStore()
	var wg sync.WaitGroup
	for i := 0; i < 50; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, _ = s.Crear("tarea")
		}()
	}
	wg.Wait()

	if n := len(s.Listar()); n != 50 {
		t.Fatalf("tareas = %d, esperado 50", n)
	}
}
