package webreports

import (
	"bufio"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"

	"aguagdl/api/internal/store"
)

// journal is an append-only, fsynced acknowledgement log. A report is acknowledged only
// after its line reaches disk. Successful database flushes compact the log atomically; a
// crash before compaction is safe because Postgres de-duplicates the random receipt.
type journal struct {
	file *os.File
	path string
}

func openJournal(path string) (*journal, error) {
	if path == "" {
		return nil, errors.New("empty web report WAL path")
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return nil, err
	}
	f, err := os.OpenFile(path, os.O_CREATE|os.O_RDWR|os.O_APPEND, 0o600)
	if err != nil {
		return nil, err
	}
	return &journal{file: f, path: path}, nil
}

func (j *journal) replay() ([]store.WebReport, error) {
	if _, err := j.file.Seek(0, io.SeekStart); err != nil {
		return nil, err
	}
	s := bufio.NewScanner(j.file)
	s.Buffer(make([]byte, 4096), 64*1024)
	var out []store.WebReport
	for s.Scan() {
		var r store.WebReport
		if err := json.Unmarshal(s.Bytes(), &r); err != nil {
			return nil, fmt.Errorf("web report WAL: %w", err)
		}
		if r.RequestID == "" {
			return nil, errors.New("web report WAL: report without receipt")
		}
		out = append(out, r)
	}
	if err := s.Err(); err != nil {
		return nil, err
	}
	_, err := j.file.Seek(0, io.SeekEnd)
	return out, err
}

func receipt() (string, error) {
	var id [16]byte
	if _, err := rand.Read(id[:]); err != nil {
		return "", err
	}
	return hex.EncodeToString(id[:]), nil
}

// append is called with the board lock held, so lines cannot interleave with compaction.
func (j *journal) append(r *store.WebReport) error {
	id, err := receipt()
	if err != nil {
		return err
	}
	r.RequestID = id
	line, err := json.Marshal(r)
	if err != nil {
		return err
	}
	if _, err := j.file.Write(append(line, '\n')); err != nil {
		return err
	}
	return j.file.Sync()
}

// rewrite is called with the board lock held after a successful database flush.
func (j *journal) rewrite(rs []store.WebReport) error {
	tmp, err := os.OpenFile(j.path+".tmp", os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0o600)
	if err != nil {
		return err
	}
	ok := false
	defer func() {
		tmp.Close()
		if !ok {
			os.Remove(tmp.Name())
		}
	}()
	enc := json.NewEncoder(tmp)
	for _, r := range rs {
		if err := enc.Encode(r); err != nil {
			return err
		}
	}
	if err := tmp.Sync(); err != nil {
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	if err := os.Rename(tmp.Name(), j.path); err != nil {
		return err
	}
	if dir, err := os.Open(filepath.Dir(j.path)); err == nil {
		err = dir.Sync()
		dir.Close()
		if err != nil {
			return err
		}
	}
	if err := j.file.Close(); err != nil {
		return err
	}
	j.file, err = os.OpenFile(j.path, os.O_RDWR|os.O_APPEND, 0o600)
	if err == nil {
		ok = true
	}
	return err
}

func (j *journal) close() error { return j.file.Close() }
