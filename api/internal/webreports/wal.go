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
	torn bool // a failed append couldn't be cut off; the next one starts a new line
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
	dropped := 0
	for s.Scan() {
		var r store.WebReport
		if err := json.Unmarshal(s.Bytes(), &r); err != nil || r.RequestID == "" {
			// A torn tail (crash between write and fsync) or a corrupt line must not
			// brick startup: skip it and compact the log below. A dropped line was
			// never acknowledged, or was already flushed to Postgres, which
			// de-duplicates by receipt.
			dropped++
			continue
		}
		out = append(out, r)
	}
	switch err := s.Err(); {
	case errors.Is(err, bufio.ErrTooLong):
		// An oversized line is corruption (writes are small); the rest of the file is
		// dropped with it by the compaction below.
		dropped++
	case err != nil:
		return nil, fmt.Errorf("web report WAL: %w", err)
	}
	if dropped > 0 {
		if err := j.rewrite(out); err != nil {
			return nil, fmt.Errorf("salvage web report WAL: %w", err)
		}
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
	if j.file == nil { // rewrite renamed the file but couldn't reopen it
		if j.file, err = os.OpenFile(j.path, os.O_RDWR|os.O_APPEND, 0o600); err != nil {
			j.file = nil
			return err
		}
	}
	info, err := j.file.Stat()
	if err != nil {
		return err
	}
	rec := append(line, '\n')
	if j.torn {
		rec = append([]byte{'\n'}, rec...)
	}
	// On failure, cut the file back so a torn line can't swallow the next report and an
	// unacknowledged one can't replay; replay skips the fragment if the cut fails too.
	if _, err := j.file.Write(rec); err != nil {
		j.torn = j.file.Truncate(info.Size()) != nil
		return err
	}
	if err := j.file.Sync(); err != nil {
		j.torn = j.file.Truncate(info.Size()) != nil
		return err
	}
	j.torn = false
	return nil
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
	ok = true
	// The handle must follow the path now: appends to the old, unlinked file would be
	// acknowledged and never replayed. If the reopen fails, j.file is nil and the next
	// append retries it.
	old := j.file
	j.file, err = os.OpenFile(j.path, os.O_RDWR|os.O_APPEND, 0o600)
	old.Close()
	if err != nil {
		j.file = nil
		return err
	}
	j.torn = false
	if dir, err := os.Open(filepath.Dir(j.path)); err == nil {
		err = dir.Sync()
		dir.Close()
		if err != nil {
			return err
		}
	}
	return nil
}

func (j *journal) close() error { return j.file.Close() }
