package repository

import "errors"

var ErrNotFound = errors.New("not found")

type Entity interface {
	GetID() int
}

type Repository interface {
	Find(id int) (Entity, error)
	Save(entity Entity) error
}

type User struct {
	ID   int
	Name string
}

func (u *User) GetID() int {
	return u.ID
}

type UserRepo struct {
	users map[int]*User
}

func (r *UserRepo) Find(id int) (*User, error) {
	if u, ok := r.users[id]; ok {
		return u, nil
	}
	return nil, ErrNotFound
}
